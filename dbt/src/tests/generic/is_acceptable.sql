{#
    NOT REPLAYABLE out of the box: relies on the udf.is_restaurant_acceptable Snowflake UDF,
    created by hand outside this project (snowflake/jev_udf.sql), which calls the paid
    OpenRouter API (one HTTP call per row). Its usage in _catalog__sources.yml stays
    commented out so the rest of the project runs without the UDF; only uncomment it
    once the UDF exists in the account.
#}
{% test is_acceptable(model, column_name, threshold=0.5) %}

    select *
    from (
        select
            *,
            {{ target.database }}.udf.is_restaurant_acceptable({{ column_name }}) as acceptability_score
        from {{ model }}
        where {{ column_name }} is not null
    )
    where acceptability_score < {{ threshold }}

{% endtest %}
