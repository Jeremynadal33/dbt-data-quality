

    select *
    from (
        select
            *,
            jnadal_db.udf.is_restaurant_acceptable(comment) as acceptability_score
        from jnadal_db.raw.restaurants
        where comment is not null
    )
    where acceptability_score < 0.5

