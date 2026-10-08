{#
    NOT REPLAYABLE out of the box: relies on the udf.ai_decide Snowflake UDF, created by hand
    outside this project (data_generator/snowflake/jev_udf.sql), which calls the paid
    OpenRouter API (one HTTP call per row). Its usage in _catalog__sources.yml stays
    commented out so the rest of the project runs without the UDF; only uncomment it
    once the UDF exists in the account.
#}
{% test is_acceptable(model, column_name, threshold=0.5) %}

{% set questions = {
    "is_acceptable": {
        "type": "noul",
        "instructions": "The input is a free-text comment about a restaurant listed on a food delivery marketplace, usually written in French. Decide whether the restaurant is acceptable to keep on the platform, based only on this comment. Read negations literally: 'aucun lien avec des gang' does not describe a criminal activity.",
        "criteria": {
            "true": "The comment describes an ordinary restaurant: food, cuisine, decor, theme, ambiance, service, opening hours or prices. Negative opinions about quality are still acceptable.",
            "false": "The comment states or strongly implies an illegal or harmful activity at or through the restaurant: money laundering, front business, organized crime, drug dealing, fraud or violence."
        }
    }
} %}

    with decisions as (
        select
            *,
            {{ target.database }}.udf.ai_decide({{ column_name }}, $${{ tojson(questions) }}$$) as decision
        from {{ model }}
        where {{ column_name }} is not null
    ),

    scored as (
        select
            * exclude (decision),
            decision:response.answers.is_acceptable.noul::float as acceptability_score,
            decision:error_message::string as error_message
        from decisions
    )

    {# An API error is reported as a failure rather than silently passing #}
    select *
    from scored
    where error_message is not null
        or acceptability_score < {{ threshold }}

{% endtest %}
