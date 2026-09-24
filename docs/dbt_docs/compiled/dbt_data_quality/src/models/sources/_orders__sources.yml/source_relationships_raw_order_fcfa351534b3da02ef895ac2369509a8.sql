
    
    

with child as (
    select item_id as from_field
    from jnadal_db.raw.order_lines
    where item_id is not null
),

parent as (
    select item_id as to_field
    from jnadal_db.raw.menu_items
)

select
    from_field

from child
left join parent
    on child.from_field = parent.to_field

where parent.to_field is null


