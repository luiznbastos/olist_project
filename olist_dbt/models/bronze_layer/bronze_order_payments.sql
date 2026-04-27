{{ config(materialized='external', format='parquet') }}
select
    order_id,
    payment_sequential::integer   as payment_sequential,
    payment_type,
    payment_installments::integer as payment_installments,
    payment_value::double         as payment_value
from {{ ref('raw_order_payments') }}
