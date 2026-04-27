{{ config(materialized='external', format='parquet') }}
select
    p.product_id,
    p.product_category_name,
    coalesce(t.product_category_name_english, p.product_category_name) as product_category_name_english,
    p.product_name_lenght::integer        as product_name_length,
    p.product_description_lenght::integer as product_description_length,
    p.product_photos_qty::integer         as product_photos_qty,
    p.product_weight_g::double            as product_weight_g,
    p.product_length_cm::double           as product_length_cm,
    p.product_height_cm::double           as product_height_cm,
    p.product_width_cm::double            as product_width_cm
from {{ ref('raw_products') }} p
left join {{ ref('raw_product_category_name_translation') }} t
    on p.product_category_name = t.product_category_name
