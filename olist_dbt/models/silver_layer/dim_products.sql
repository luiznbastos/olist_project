{{ config(materialized='external', format='parquet') }}
with product_metrics as (
    select
        product_id,
        count(distinct order_id)  as total_orders,
        round(avg(price), 2)      as avg_price
    from {{ ref('bronze_order_items') }}
    group by product_id
),
product_reviews as (
    select
        oi.product_id,
        round(avg(r.review_score), 2) as avg_rating,
        count(r.review_id)            as total_reviews
    from {{ ref('bronze_order_items') }} oi
    left join {{ ref('bronze_order_reviews') }} r using (order_id)
    group by oi.product_id
)
select
    p.product_id,
    p.product_category_name,
    p.product_category_name_english,
    coalesce(m.total_orders, 0)  as total_orders,
    m.avg_price,
    r.avg_rating,
    coalesce(r.total_reviews, 0) as total_reviews
from {{ ref('bronze_products') }} p
left join product_metrics m using (product_id)
left join product_reviews r using (product_id)
