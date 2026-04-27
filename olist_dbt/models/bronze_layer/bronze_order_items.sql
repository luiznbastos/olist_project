{{ config(materialized='external', format='parquet') }}
select
    order_id,
    order_item_id::integer         as order_item_id,
    product_id,
    seller_id,
    shipping_limit_date::timestamp as shipping_limit_date,
    price::double                  as price,
    freight_value::double          as freight_value
from {{ ref('raw_order_items') }}
