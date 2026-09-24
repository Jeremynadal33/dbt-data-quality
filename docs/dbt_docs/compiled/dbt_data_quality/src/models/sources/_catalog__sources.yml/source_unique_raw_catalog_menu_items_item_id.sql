
    
    

select
    item_id as unique_field,
    count(*) as n_records

from jnadal_db.raw.menu_items
where item_id is not null
group by item_id
having count(*) > 1


