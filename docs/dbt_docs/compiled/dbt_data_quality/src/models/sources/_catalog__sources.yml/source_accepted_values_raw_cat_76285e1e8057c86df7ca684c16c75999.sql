
    
    

with all_values as (

    select
        category as value_field,
        count(*) as n_records

    from jnadal_db.raw.menu_items
    group by category

)

select *
from all_values
where value_field not in (
    'starter','main','dessert','drink','side'
)


