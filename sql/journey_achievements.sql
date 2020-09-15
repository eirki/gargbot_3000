-- name: most_steps_one_day_individual
with journey_step as (
    select
        amount,
        gargling_id,
        taken_at
    from
        step
    where
        journey_id = :journey_id
        and (
            :taken_before is null
            or taken_at <= :taken_before
        )
        and (
            :less_than is null
            or amount < :less_than
        )
)
select
    *
from
    journey_step
where
    amount = (
        select
            max(amount)
        from
            journey_step
    );


-- name: most_steps_one_day_collective
with grouped as (
    select
        sum(amount) as amount,
        taken_at
    from
        step
    where
        journey_id = :journey_id
        and (
            :taken_before is null
            or taken_at <= :taken_before
        )
    group by
        taken_at
)
select
    amount,
    taken_at
from
    grouped
where
    amount = (
        select
            max(amount)
        from
            grouped
    );


-- name: highest_share
with journey_step_avgs as (
    select
        step.taken_at,
        step.gargling_id,
        (step.amount :: decimal / avgs.sum_amount) as amount
    from
        step
        inner join (
            select
                sum(amount) as sum_amount,
                taken_at
            from
                step
            where
                journey_id = :journey_id
                and (
                    :taken_before is null
                    or step.taken_at <= :taken_before
                )
            group by
                taken_at
        ) as avgs on step.taken_at = avgs.taken_at
    where
        journey_id = :journey_id
)
select
    round(amount * 100) :: int as amount,
    gargling_id,
    taken_at
from
    journey_step_avgs
where
    amount = (
        select
            max(amount)
        from
            journey_step_avgs
    );


-- name: biggest_improvement_individual
with journey_step_imp as (
    select
        step.taken_at,
        step.gargling_id,
        (step.amount - yesterday.amount) as amount
    from
        step
        inner join (
            select
                amount,
                gargling_id,
                taken_at + interval '1 day' as taken_at
            from
                step
            where
                journey_id = :journey_id
        ) as yesterday on step.taken_at = yesterday.taken_at
        and step.gargling_id = yesterday.gargling_id
    where
        journey_id = :journey_id
        and (
            :taken_before is null
            or step.taken_at <= :taken_before
        )
)
select
    amount,
    gargling_id,
    taken_at
from
    journey_step_imp
where
    amount = (
        select
            max(amount)
        from
            journey_step_imp
    );


-- name: biggest_improvement_collective
with grouped as (
    select
        sum(amount) as amount,
        taken_at
    from
        step
    where
        journey_id = :journey_id
        and (
            :taken_before is null
            or taken_at <= :taken_before
        )
    group by
        taken_at
),
grouped_imp as (
    select
        grouped.taken_at,
        (grouped.amount - yesterday.amount) as amount
    from
        grouped
        inner join (
            select
                amount,
                taken_at + interval '1 day' as taken_at
            from
                grouped
        ) as yesterday on grouped.taken_at = yesterday.taken_at
)
select
    amount,
    taken_at
from
    grouped_imp
where
    amount = (
        select
            max(amount)
        from
            grouped_imp
    );


-- name: longest_streak
with streaks as (
    /* #3 grouped by streak id*/
    select
        count(*) as amount,
        gargling_id,
        max(taken_at) as taken_at
    from
        (
            /* #2 streak_id for each day*/
            select
                step.taken_at,
                step.gargling_id,
                step.taken_at - ('1970-01-01' :: date) - row_number() over (
                    partition by step.gargling_id
                    order by
                        step.taken_at
                ) as streak_id
            from
                step
                inner join (
                    /* #1 largest amount for each day*/
                    select
                        max(amount) as amount,
                        taken_at
                    from
                        step
                    where
                        journey_id = :journey_id
                    group by
                        taken_at
                ) as avgs on step.taken_at = avgs.taken_at
                and step.amount = avgs.amount
            where
                journey_id = :journey_id
                and (
                    :taken_before is null
                    or step.taken_at <= :taken_before
                )
        ) as journey_step_maxs
    group by
        gargling_id,
        streak_id
)
select
    amount,
    gargling_id,
    taken_at
from
    streaks
where
    amount = (
        select
            max(amount)
        from
            streaks
    );
