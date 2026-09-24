
    
    

with child as (
    select restaurant_id as from_field
    from jnadal_db.raw.menu_items
    where restaurant_id is not null
),

parent as (
    select restaurant_id as to_field
    from jnadal_db.raw.restaurants
)

select
    from_field

from child
left join parent
    on child.from_field = parent.to_field

where parent.to_field is null


