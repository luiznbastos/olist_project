{{ config(materialized='external', format='parquet') }}
-- Grain: one row per order item.
-- Payments are pre-aggregated at order level to avoid row multiplication
-- when an order has multiple payment methods.
with payments_agg as (
    select
        order_id,
        sum(payment_value)                                           as total_payment_value,
        sum(payment_installments)                                    as total_installments,
        count(distinct payment_type)                                 as payment_methods_count,
        (array_agg(payment_type order by payment_value desc))[1]     as primary_payment_type
    from {{ ref('bronze_order_payments') }}
    group by order_id
)
select
    o.order_id,
    o.customer_id,
    o.order_status,
    oi.seller_id,
    oi.product_id,
    oi.order_item_id,
    oi.price,
    oi.freight_value,
    o.order_purchase_timestamp,
    o.order_approved_at,
    o.order_delivered_carrier_date,
    o.order_delivered_customer_date,
    o.order_estimated_delivery_date,
    p.total_payment_value,
    p.primary_payment_type,
    p.payment_methods_count,
    p.total_installments,
    datediff(
        'day',
        o.order_purchase_timestamp,
        o.order_delivered_customer_date
    )                                                                as delivery_days
-- INNER JOIN on order_items: fact grain is order-item, not order.
-- Orders with no items (canceled/unavailable before items were attached) are excluded.
from {{ ref('bronze_orders') }} o
inner join {{ ref('bronze_order_items') }} oi using (order_id)
left join payments_agg p using (order_id)
