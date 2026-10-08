-- Jev UDF: ai_decide, a generic Snowflake function asking Jev typed questions about any text.
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

-- Same name and shape as Databricks' ai_decide(state, questions): `state` is plain text or a
-- JSON object, `questions` a JSON object of Jev questions. Never raises: returns
-- {"response": {"answers": ...}, "metadata": {...}, "error_message": null | "..."},
-- so one failed API call does not fail the whole query.
create or replace function <database>.udf.ai_decide(
    state string,
    questions string,
    model string default 'typesafe/jev-1.13'
)
  returns variant
  language python
  runtime_version = '3.12'
  handler = 'decide'
  packages = ('requests')
  external_access_integrations = (openrouter_access)
  secrets = ('api_key' = <database>.udf.openrouter_api_key)
as $$
import json

import _snowflake
import requests

session = requests.Session()


def _as_state(state):
    try:
        parsed = json.loads(state)
    except ValueError:
        parsed = None
    return parsed if isinstance(parsed, dict) else {"input": state}


def _failure(model, error_message):
    return {"response": None, "metadata": {"model": model}, "error_message": error_message}


def decide(state, questions, model):
    if state is None:
        return None
    try:
        response = session.post(
            "https://openrouter.ai/api/alpha/decisions",
            headers={"Authorization": f"Bearer {_snowflake.get_generic_secret_string('api_key')}"},
            json={"model": model, "state": _as_state(state), "questions": json.loads(questions)},
            timeout=30,
        )
        if not response.ok:
            return _failure(model, f"HTTP {response.status_code}: {response.text}")
        body = response.json()
        return {
            "response": {"answers": body["answers"]},
            "metadata": {"model": body.get("model"), "usage": body.get("usage")},
            "error_message": None,
        }
    except Exception as error:
        return _failure(model, f"{type(error).__name__}: {error}")
$$;

-- The role dbt runs with (DBT_SNOWFLAKE_ROLE) must be able to call the UDF from the is_acceptable test
grant usage on function <database>.udf.ai_decide(string, string, string) to role <role>;

-- Self-contained try-out, no table needed: 5 acceptable comments (3 of them traps) and 5 unacceptable ones.
with restaurants as (
              select 'Restaurant à thème marin' as comment, true as expected_acceptable
    union all select 'Brunch le week-end, réservation conseillée', true
    union all select 'Aucun lien avec la mafia, promis, juste de très bonnes pâtes', true
    union all select 'Service lent et plats fades, à éviter', true
    union all select 'Le tiramisu est criminellement bon', true
    union all select 'C''est un repère de gangsters, à utiliser uniquement pour du blanchiment d''argent', false
    union all select 'Demandez le menu spécial au serveur : il vend aussi de la drogue', false
    union all select 'Le patron encaisse tout en liquide et ne déclare rien au fisc', false
    union all select 'Façade pour des paris clandestins dans l''arrière-salle', false
    union all select 'Le chef menace les clients qui laissent un avis négatif', false
)
select
  comment,
  expected_acceptable,
  <database>.udf.ai_decide(
    comment,
    $${
      "is_acceptable": {
        "type": "noul",
        "instructions": "The input is a free-text comment about a restaurant listed on a food delivery marketplace, usually written in French. Decide whether the restaurant is acceptable to keep on the platform, based only on this comment. Read negations literally: 'aucun lien avec des gang' does not describe a criminal activity.",
        "criteria": {
          "true": "The comment describes an ordinary restaurant: food, cuisine, decor, theme, ambiance, service, opening hours or prices. Negative opinions about quality are still acceptable.",
          "false": "The comment states or strongly implies an illegal or harmful activity at or through the restaurant: money laundering, front business, organized crime, drug dealing, fraud or violence."
        }
      }
    }$$
  ):response.answers.is_acceptable.noul::float as acceptability_score
from restaurants
order by acceptability_score;

-- After `mise run demo:chaos:new-restaurant-volume`, only the dormant restaurant should score low.
select
  restaurant_id,
  comment,
  <database>.udf.ai_decide(
    comment,
    $${
      "is_acceptable": {
        "type": "noul",
        "instructions": "The input is a free-text comment about a restaurant listed on a food delivery marketplace, usually written in French. Decide whether the restaurant is acceptable to keep on the platform, based only on this comment. Read negations literally: 'aucun lien avec des gang' does not describe a criminal activity.",
        "criteria": {
          "true": "The comment describes an ordinary restaurant: food, cuisine, decor, theme, ambiance, service, opening hours or prices. Negative opinions about quality are still acceptable.",
          "false": "The comment states or strongly implies an illegal or harmful activity at or through the restaurant: money laundering, front business, organized crime, drug dealing, fraud or violence."
        }
      }
    }$$
  ):response.answers.is_acceptable.noul::float as acceptability_score
from <database>.raw.restaurants
order by acceptability_score;

-- 0. Check what exists before dropping
show user functions like 'ai_decide' in schema <database>.udf;
show external access integrations like 'openrouter_access';
show secrets in schema <database>.udf;
show network rules in schema <database>.udf;

-- 1. UDF (the argument types are part of its identity)
drop function if exists <database>.udf.ai_decide(string, string, string);

-- 2. Account-level integration
drop external access integration if exists openrouter_access;

-- 3. Schema-level objects
drop secret if exists <database>.udf.openrouter_api_key;
drop network rule if exists <database>.udf.openrouter_egress;

-- 4. The schema itself, only if it holds nothing else
show objects in schema <database>.udf;
drop schema if exists <database>.udf;