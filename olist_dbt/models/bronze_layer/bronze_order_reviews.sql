{{ config(materialized='external', format='parquet') }}
select
    review_id,
    order_id,
    review_score::integer                          as review_score,
    coalesce(review_comment_title, 'N/A')          as review_comment_title,
    coalesce(review_comment_message, 'N/A')        as review_comment_message,
    review_creation_date::timestamp                as review_creation_date,
    review_answer_timestamp::timestamp             as review_answer_timestamp
from {{ ref('raw_order_reviews') }}
