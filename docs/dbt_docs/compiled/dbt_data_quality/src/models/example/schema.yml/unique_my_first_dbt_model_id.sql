
    
    

select
    id as unique_field,
    count(*) as n_records

from jnadal_db.jnadal_db.my_first_dbt_model
where id is not null
group by id
having count(*) > 1


