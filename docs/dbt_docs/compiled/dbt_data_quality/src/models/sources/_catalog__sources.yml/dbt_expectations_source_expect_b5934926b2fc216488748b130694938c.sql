




    with grouped_expression as (
    select
        
        
    
  


    
regexp_instr(contact_email, '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$', 1, 1, 0, '')


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




