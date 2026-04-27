{{ config(materialized='view') }}
select * from read_parquet('{{ var("data_lake_path") }}/raw/olist_order_items_dataset.parquet')
