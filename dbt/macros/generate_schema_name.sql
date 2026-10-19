{# Utilise "silver"/"gold" tels quels au lieu de "analytics_silver"/"analytics_gold" #}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {{ custom_schema_name | trim if custom_schema_name else target.schema }}
{%- endmacro %}