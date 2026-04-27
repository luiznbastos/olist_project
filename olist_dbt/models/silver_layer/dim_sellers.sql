{{ config(materialized='external', format='parquet') }}
with seller_metrics as (
    select
        oi.seller_id,
        count(distinct oi.order_id)    as total_orders,
        sum(oi.price)                  as total_revenue,
        round(avg(r.review_score), 2)  as avg_rating
    from {{ ref('bronze_order_items') }} oi
    left join {{ ref('bronze_order_reviews') }} r using (order_id)
    group by oi.seller_id
)
select
    s.seller_id,
    s.seller_city,
    s.seller_state,
    coalesce(m.total_orders, 0)  as total_orders,
    coalesce(m.total_revenue, 0) as total_revenue,
    m.avg_rating
from {{ ref('bronze_sellers') }} s
left join seller_metrics m using (seller_id)
