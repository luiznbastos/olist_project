{# Use the custom schema name directly — avoids the default {target}_{custom} pattern
   that would produce main_bronze, main_silver, etc. instead of bronze, silver, gold. #}
{% macro generate_schema_name(custom_schema_name, node) %}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{% endmacro %}
