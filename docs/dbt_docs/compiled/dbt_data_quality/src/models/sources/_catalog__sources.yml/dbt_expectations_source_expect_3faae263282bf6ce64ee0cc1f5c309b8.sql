




    with grouped_expression as (
    select
        
        
    
  


    
regexp_instr(sku, '^[A-Z]{3}-[0-9]{5}$', 1, 1, 0, '')


 > 0
 as expression


    from jnadal_db.raw.menu_items
    

),
validation_errors as (

    select
        *
    from
        grouped_expression
    where
        not(expression = true)

)

select *
from validation_errors




