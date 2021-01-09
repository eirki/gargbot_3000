--name: steps_pie
select
    sum(step.amount) as y,
    min(gargling.color_hex) as color,
    gargling.first_name as name
from
    step
    left join gargling on step.gargling_id = gargling.id
where
    journey_id = :journey_id
group by
    gargling.first_name;


--name: first_place_pie
select
    gargling.first_name as name,
    min(gargling.color_hex) as color,
    count(gargling.first_name) as y
from
    (
        select
            max(step.amount) as amount,
            step.taken_at
        from
            step
        where
            journey_id = :journey_id
        group by
            step.taken_at
    ) as max_step
    left join step on max_step.amount = step.amount
    and max_step.taken_at = step.taken_at
    left join gargling on step.gargling_id = gargling.id
group by
    gargling.first_name;


-- name: above_median_pie
select
    gargling.first_name as name,
    min(gargling.color_hex) as color,
    count(gargling.first_name) as y
from
    step
    left join (
        select
            taken_at,
            percentile_cont(0.5) within group (
                order by
                    amount
            ) as amount
        from
            step
        where
            journey_id = :journey_id
        group by
            taken_at
    ) as median on median.taken_at = step.taken_at
    left join gargling on step.gargling_id = gargling.id
where
    step.amount >= median.amount
    and step.journey_id = :journey_id
group by
    gargling.first_name;


-- name: contributing_days_pie
select
    gargling.first_name as name,
    min(gargling.color_hex) as color,
    count(gargling.first_name) as y
from
    step
    left join gargling on step.gargling_id = gargling.id
where
    step.amount > 0
    and step.journey_id = :journey_id
group by
    gargling.first_name;


--name: distance_area
with step_with_avg as (
    select
        gargling_id,
        taken_at,
        amount
    from
        step
    union
    all
    select
        -1 as gargling_id,
        taken_at,
        avg(amount) :: int as amount
    from
        step
    where
        journey_id = :journey_id
    group by
        taken_at
),
gargling_with_avg as (
    select
        id,
        first_name,
        color_hex
    from
        gargling
    union
    all
    select
        -1 as id,
        'Average' as first_name,
        '#808080' as color_hex
)
select
    gargling_with_avg.first_name as name,
    gargling_with_avg.color_hex as color,
    24 * 3600 * 1000 as "pointInterval",
    all_date_steps.*
from
    (
        select
            gargling_with_avg.id as gargling_id,
            array_agg(
                coalesce(step_with_avg.amount, 0)
                order by
                    all_dates.taken_at asc
            ) as data,
            extract(
                epoch
                from
                    min(all_dates.taken_at)
            ) * 1000 as "pointStart",
            sum(step_with_avg.amount) as sum_amount
        from
            gargling_with_avg
            cross join (
                select
                    distinct(taken_at) as taken_at
                from
                    step_with_avg
            ) as all_dates
            left join step_with_avg on (
                gargling_with_avg.id = step_with_avg.gargling_id
                and all_dates.taken_at = step_with_avg.taken_at
            )
        group by
            gargling_with_avg.id
    ) as all_date_steps
    left join gargling_with_avg on all_date_steps.gargling_id = gargling_with_avg.id
order by
    case
        when all_date_steps.gargling_id = :gargling_id then 1
        when all_date_steps.gargling_id = -1 then -1
        else 0
    end,
    sum_amount asc;


--name: personal_stats
with gargling_data as (
    select
        gargling.first_name as name,
        (grouped.total_steps * 0.75) :: int as total_distance,
        grouped.*
    from
        gargling
        left join (
            select
                sum(amount) as total_steps,
                max(amount) as max_steps,
                avg(amount) :: int as avg_steps,
                gargling_id
            from
                step
            where
                journey_id = :journey_id
            group by
                gargling_id
        ) as grouped on gargling.id = grouped.gargling_id
)
select
    *
from
    gargling_data
union
all
select
    'Average' as name,
    avg(total_distance) :: int as total_distance,
    avg(total_steps) :: int as total_steps,
    avg(max_steps) :: int as max_steps,
    avg(avg_steps) :: int as avg_steps,
    -1 as gargling_id
from
    gargling_data
