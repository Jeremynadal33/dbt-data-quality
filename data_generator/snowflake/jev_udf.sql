-- Jev UDF: scores whether a restaurant is acceptable from its free-text `comment`.
-- Run once, by hand, in a Snowflake worksheet. Replace <database>, <role> and <openrouter_api_key>.
--
-- NOT REPLAYABLE by the project: no mise task or CI job runs this file, and the UDF calls
-- the paid OpenRouter API. It backs the custom dbt test dbt/src/tests/generic/is_acceptable.sql,
-- whose usage in dbt/src/models/sources/_catalog__sources.yml stays commented out so the
-- rest of the project runs without it. Uncomment it only once this UDF exists.
--
-- Everything lives in its own `udf` schema on purpose: `mise run demo:reset` drops
-- `raw`, `dq_failures` and `elementary` with CASCADE, which would take the UDF and its
-- secret with them.

use role accountadmin;

create schema if not exists <database>.udf;

create or replace network rule <database>.udf.openrouter_egress
  mode = egress
  type = host_port
  value_list = ('openrouter.ai:443');

create or replace secret <database>.udf.openrouter_api_key
  type = generic_string
  secret_string = '<openrouter_api_key>';

create or replace external access integration openrouter_access
  allowed_network_rules = (<database>.udf.openrouter_egress)
  allowed_authentication_secrets = (<database>.udf.openrouter_api_key)
  enabled = true;

-- Only needed if the UDF is created/called by a role other than accountadmin
grant usage on integration openrouter_access to role <role>;
grant usage on schema <database>.udf to role <role>;
grant read on secret <database>.udf.openrouter_api_key to role <role>;

-- Returns a score in [0, 1]: close to 1 = acceptable, close to 0 = unacceptable.
create or replace function <database>.udf.is_restaurant_acceptable(restaurant_comment string)
  returns float
  language python
  runtime_version = '3.12'
  handler = 'score'
  packages = ('requests')
  external_access_integrations = (openrouter_access)
  secrets = ('api_key' = <database>.udf.openrouter_api_key)
as $$
import _snowflake
import requests

session = requests.Session()

QUESTION = {
    "type": "noul",
    "instructions": (
        "The input is a free-text comment about a restaurant listed on a food delivery "
        "marketplace, usually written in French. Decide whether the restaurant is acceptable "
        "to keep on the platform, based only on this comment. Read negations literally: "
        "'aucun lien avec la mafia' does not describe a criminal activity."
    ),
    "criteria": {
        "true": (
            "The comment describes an ordinary restaurant: food, cuisine, decor, theme, "
            "ambiance, service, opening hours or prices. Negative opinions about quality "
            "(slow service, bland food) are still acceptable."
        ),
        "false": (
            "The comment states or strongly implies an illegal or harmful activity at or "
            "through the restaurant: money laundering, front business, organized crime, drug "
            "dealing, fraud or violence."
        ),
    },
}


def score(restaurant_comment):
    if restaurant_comment is None:
        return None
    response = session.post(
        "https://openrouter.ai/api/alpha/decisions",
        headers={"Authorization": f"Bearer {_snowflake.get_generic_secret_string('api_key')}"},
        json={
            "model": "typesafe/jev-1.13",
            "state": {"input": restaurant_comment},
            "questions": {"is_acceptable": QUESTION},
        },
        timeout=30,
    )
    response.raise_for_status()
    return response.json()["answers"]["is_acceptable"]["noul"]
$$;

-- The role dbt runs with (DBT_SNOWFLAKE_ROLE) must be able to call the UDF from the is_acceptable test
grant usage on function <database>.udf.is_restaurant_acceptable(string) to role <role>;

-- After `mise run demo:chaos:new-restaurant-volume`, only the dormant restaurant should score low.
select
  restaurant_id,
  comment,
  <database>.udf.is_restaurant_acceptable(comment) as acceptability_score
from <database>.raw.restaurants
order by acceptability_score;

-- 0. Check what exists before dropping
show user functions like 'is_restaurant_acceptable' in schema <database>.udf;
show external access integrations like 'openrouter_access';
show secrets in schema <database>.udf;
show network rules in schema <database>.udf;

-- 1. UDF (the argument types are part of its identity)
drop function if exists <database>.udf.is_restaurant_acceptable(string);

-- 2. Account-level integration
drop external access integration if exists openrouter_access;

-- 3. Schema-level objects
drop secret if exists <database>.udf.openrouter_api_key;
drop network rule if exists <database>.udf.openrouter_egress;

-- 4. The schema itself, only if it holds nothing else
show objects in schema <database>.udf;
drop schema if exists <database>.udf;