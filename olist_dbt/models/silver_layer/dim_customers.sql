{{ config(materialized='external', format='parquet') }}
with customer_metrics as (
    select
        o.customer_id,
        avg(oi.price)                                                               as avg_order_value,
        sum(case when o.order_status = 'delivered' then oi.price else 0 end)        as total_spent,
        sum(case when o.order_status = 'delivered' then 1 else 0 end)               as total_delivered_orders,
        round(avg(
            case when o.order_delivered_customer_date is not null
                 then datediff('day', o.order_purchase_timestamp, o.order_delivered_customer_date)
            end
        ), 0)                                                                       as avg_delivery_days
    from {{ ref('bronze_orders') }} o
    left join {{ ref('bronze_order_items') }} oi using (order_id)
    group by o.customer_id
)
select
    c.customer_id,
    c.customer_unique_id,
    c.customer_city,
    c.customer_state,
    coalesce(m.avg_order_value, 0)        as avg_order_value,
    coalesce(m.total_spent, 0)            as total_spent,
    coalesce(m.total_delivered_orders, 0) as total_delivered_orders,
    m.avg_delivery_days
from {{ ref('bronze_customers') }} c
left join customer_metrics m using (customer_id)
