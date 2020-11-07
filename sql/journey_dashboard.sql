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
select
    gargling.first_name as name,
    gargling.color_hex as color,
    24 * 3600 * 1000 as "pointInterval",
    all_date_steps.*
from
    (
        select
            gargling.id as gargling_id,
            array_agg(
                coalesce(step.amount, 0)
                order by
                    all_dates.taken_at asc
            ) as data,
            extract(
                epoch
                from
                    min(all_dates.taken_at)
            ) * 1000 as "pointStart",
            sum(step.amount) as sum_amount
        from
            gargling
            cross join (
                select
                    distinct(taken_at) as taken_at,
                    journey_id
                from
                    step
                where
                    journey_id = :journey_id
            ) as all_dates
            left join step on (
                gargling.id = step.gargling_id
                and all_dates.taken_at = step.taken_at
                and step.journey_id = all_dates.journey_id
            )
        group by
            gargling.id
    ) as all_date_steps
    left join gargling on all_date_steps.gargling_id = gargling.id
order by
    case
        when all_date_steps.gargling_id = :gargling_id then 1
        else 0
    end,
    sum_amount asc;


--name: personal_stats
select
    gargling.first_name as name,
    grouped.total_steps * 0.75 :: real as total_distance,
    grouped.*
from
    gargling
    left join (
        select
            sum(amount) as total_steps,
            max(amount) as max_steps,
            round(avg(amount), 1) :: real as avg_steps,
            gargling_id
        from
            step
        where
            journey_id = :journey_id
        group by
            gargling_id
    ) as grouped on gargling.id = grouped.gargling_id;
