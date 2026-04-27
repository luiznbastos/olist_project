{{ config(materialized='external', format='parquet') }}
select
    geolocation_zip_code_prefix,
    geolocation_lat::double       as geolocation_lat,
    geolocation_lng::double       as geolocation_lng,
    lower(trim(geolocation_city)) as geolocation_city,
    upper(trim(geolocation_state)) as geolocation_state
from {{ ref('raw_geolocation') }}
