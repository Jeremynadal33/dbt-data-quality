
    
    

with all_values as (

    select
        cuisine_type as value_field,
        count(*) as n_records

    from jnadal_db.raw.restaurants
    group by cuisine_type

)

select *
from all_values
where value_field not in (
    'italian','japanese','french','indian','lebanese','mexican'
)


