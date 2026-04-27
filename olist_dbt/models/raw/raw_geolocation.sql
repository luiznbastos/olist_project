{{ config(materialized='view') }}
select * from read_parquet('{{ var("data_lake_path") }}/raw/olist_geolocation_dataset.parquet')
