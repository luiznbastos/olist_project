{{ config(materialized='external', format='parquet') }}
-- One row per zip code prefix. Raw table has ~1M rows with many duplicates per zip.
-- lat/lng: centroid (avg). city/state: most frequent value for the prefix.
select
    geolocation_zip_code_prefix,
    round(avg(geolocation_lat), 6)  as geolocation_lat,
    round(avg(geolocation_lng), 6)  as geolocation_lng,
    mode(geolocation_city)          as geolocation_city,
    mode(geolocation_state)         as geolocation_state
from {{ ref('bronze_geolocation') }}
group by geolocation_zip_code_prefix
