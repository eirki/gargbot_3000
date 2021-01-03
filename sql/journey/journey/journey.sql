-- name: create_schema#
create table journey (
    id serial primary key,
    origin text not null,
    destination text not null,
    ongoing boolean not null,
    started_at date,
    finished_at date
);


create unique index on journey (ongoing)
where
    ongoing = true;


create table waypoint (
    id serial primary key,
    journey_id smallint not null references journey(id),
    lat double precision not null,
    lon double precision not null,
    elevation float,
    distance float not null
);


create table step (
    journey_id smallint not null references journey(id),
    gargling_id smallint not null references gargling(id),
    taken_at date not null,
    amount smallint not null
);


create unique index on step (journey_id, gargling_id, taken_at);


create table location (
    journey_id smallint not null references journey(id),
    latest_waypoint smallint not null references waypoint(id),
    lat double precision not null,
    lon double precision not null,
    distance int not null,
    date date not null,
    address text,
    country text,
    poi text,
    photo_url text
);


-- name: add_journey<!
insert into
    journey (origin, destination, ongoing)
values
    (:origin, :destination, false) returning id;


-- name: start_journey!
update
    journey
set
    ongoing = true,
    started_at = :date
where
    id = :journey_id;


-- name: stop_journey!
update
    journey
set
    ongoing = false
where
    id = :journey_id;


-- name: delete_journey!
delete from
    location
where
    journey_id = :journey_id;


delete from
    waypoint
where
    journey_id = :journey_id;


delete from
    journey
where
    id = :journey_id;


-- name: finish_journey!
update
    journey
set
    finished_at = :date
where
    id = :journey_id;


-- name: get_ongoing_journey^
select
    *
from
    journey
where
    ongoing = true
    and finished_at is null;


-- name: all_journeys
select
    *
from
    journey
    left join (
        select
            journey_id as id,
            count(*) as n_waypoints
        from
            waypoint
        group by
            journey_id
    ) as n_waypoints on journey.id = n_waypoints.id
    left join (
        select
            journey_id,
            latest_waypoint,
            lat as loc_lat,
            lon as loc_lon,
            distance,
            date as loc_date
        from
            (
                select
                    *,
                    row_number() over (
                        partition by journey_id
                        order by
                            date desc
                    ) as row_num
                from
                    location
            ) as locs
        where
            row_num = 1
    ) as location on journey.id = location.journey_id;


-- name: get_journey^
select
    *,
    (
        select
            distance
        from
            waypoint
        where
            journey_id = :journey_id
        order by
            distance desc
        fetch first
            row only
    ) as distance
from
    journey
where
    id = :journey_id;


-- name: add_waypoints*!
insert into
    waypoint (journey_id, lat, lon, distance, elevation)
values
    (:journey_id, :lat, :lon, :distance, :elevation);


-- name: waypoints_for_journey
select
    *
from
    waypoint
where
    journey_id = :journey_id;


-- name: waypoints_between_distances
select
    lon,
    lat,
    elevation,
    distance
from
    waypoint
where
    journey_id = :journey_id
    and (
        distance between :low
        and :high
    )
order by
    distance;


-- name: get_waypoint_for_distance^
select
    *
from
    waypoint
where
    journey_id = :journey_id
    and :distance > distance
order by
    distance desc
fetch first
    row only;


-- name: get_next_waypoint_for_waypoint^
select
    *
from
    waypoint
where
    journey_id = :journey_id
    and id = :waypoint_id + 1;


-- name: add_location!
insert into
    location (
        journey_id,
        latest_waypoint,
        lat,
        lon,
        distance,
        date,
        address,
        country,
        poi
    )
values
    (
        :journey_id,
        :latest_waypoint,
        :lat,
        :lon,
        :distance,
        :date,
        :address,
        :country,
        :poi
    );


-- name: most_recent_location^
select
    *
from
    location
where
    journey_id = :journey_id
order by
    date desc
fetch first
    row only;


-- name: location_between_distances
select
    lat,
    lon
from
    location
where
    journey_id = :journey_id
    and (
        distance between :low
        and :high
    )
order by
    distance;


-- name: locations_for_journey
select
    *
from
    location
where
    journey_id = :journey_id
order by
    date;


-- name: add_steps*!
insert into
    step (journey_id, gargling_id, taken_at, amount)
values
    (
        :journey_id,
        :gargling_id,
        :taken_at,
        :amount
    );


-- name: colors_names_for_ids
select
    id,
    first_name,
    color_name,
    color_hex
from
    gargling
where
    id = any(:ids);


-- name: get_steps
select
    step.*,
    gargling.first_name,
    gargling.color_hex
from
    step
    left join gargling on step.gargling_id = gargling.id
where
    step.journey_id = :journey_id;


--name: weekly_summary
select
    sum(step.amount) as amount,
    gargling.first_name
from
    step
    left join gargling on step.gargling_id = gargling.id
where
    step.journey_id = :journey_id
    and step.taken_at > :date - interval '7 days'
group by
    first_name;
