{{ config(materialized='external', format='parquet') }}
with date_spine as (
    select unnest(generate_series(
        '2016-01-01'::date,
        '2019-12-31'::date,
        interval '1 day'
    ))::date as date_day
)
select
    date_day,
    extract(year    from date_day)::integer  as year,
    extract(quarter from date_day)::integer  as quarter,
    extract(month   from date_day)::integer  as month_number,
    strftime(date_day, '%B')                 as month_name,
    extract(week    from date_day)::integer  as week_of_year,
    -- isodow: 1=Monday … 7=Sunday
    extract(isodow  from date_day)::integer  as day_of_week,
    strftime(date_day, '%A')                 as day_name,
    extract(isodow  from date_day) >= 6      as is_weekend,
    date_trunc('month',   date_day)::date    as first_day_of_month,
    date_trunc('quarter', date_day)::date    as first_day_of_quarter,
    date_trunc('year',    date_day)::date    as first_day_of_year,
    'Q' || extract(quarter from date_day)::integer
        || ' ' || extract(year from date_day)::integer  as year_quarter,
    strftime(date_day, '%Y-%m')              as year_month
from date_spine
