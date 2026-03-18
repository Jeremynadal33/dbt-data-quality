{#
    Overriding this [dbt core macro](https://github.com/dbt-labs/dbt-adapters/blob/0aad0dff69aadf42fbf6492011a02feb009ad0b8/dbt-adapters/src/dbt/include/global_project/macros/get_custom_name/get_custom_schema.sql#L21)
    or this [dbt Fusion macro](https://github.com/dbt-labs/dbt-fusion/blob/a1112b5140eb0a3c1dc4de37fa627910f531204b/crates/dbt-loader/src/dbt_macro_assets/dbt-adapters/macros/get_custom_name/get_custom_schema.sql#L21)

    It is mandatory when using custom schema names.
#}

{% macro default__generate_schema_name(custom_schema_name, node) -%}

    {%- set default_schema = target.schema -%}
    {%- if custom_schema_name is none -%}

        {{ default_schema }}

    {%- else -%}
        {% if target.name.lower() in ['prod'] or custom_schema_name == 'elementary' %}
            {{ custom_schema_name | trim }}
        {% else %}
            {{ default_schema }}_{{ custom_schema_name | trim }}
        {% endif %}

    {%- endif -%}

{%- endmacro %}