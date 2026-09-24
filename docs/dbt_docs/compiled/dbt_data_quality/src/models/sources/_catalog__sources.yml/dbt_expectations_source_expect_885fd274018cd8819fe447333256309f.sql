




    with grouped_expression as (
    select
        
        
    
  


    
regexp_instr(siret, '^[0-9]{14}$', 1, 1, 0, '')


 > 0
 as expression


    from jnadal_db.raw.restaurants
    

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




