{{ config(materialized='view') }}
select * from read_parquet('{{ var("data_lake_path") }}/raw/product_category_name_translation.parquet')
