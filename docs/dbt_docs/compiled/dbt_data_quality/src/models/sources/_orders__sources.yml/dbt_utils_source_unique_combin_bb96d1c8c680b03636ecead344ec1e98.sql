





with validation_errors as (

    select
        order_id, line_id
    from jnadal_db.raw.order_lines
    group by order_id, line_id
    having count(*) > 1

)

select *
from validation_errors


