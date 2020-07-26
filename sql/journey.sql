-- name: create_schema#
create table journey (
    id serial primary key,
    origin text not null,
    destination text not null,
    ongoing boolean not null,
    started_at timestamptz,
    finished_at timestamptz
);


create unique index on journey (ongoing)
where
    ongoing = true;


create table waypoint (
    id serial primary key,
    journey_id smallint not null references journey(id),
    lat double precision not null,
    lon double precision not null,
    cum_dist int null
);


create table step (
    journey_id smallint not null references journey(id),
    gargling_id smallint not null references gargling(id),
    taken_at timestamptz not null,
    amount smallint not null
);


create table location (
    journey_id smallint not null references journey(id),
    latest_waypoint smallint not null references waypoint(id),
    lat double precision not null,
    lon double precision not null,
    distance int not null,
    date timestamptz not null,
    address text not null,
    img_url text not null,
    map_url text not null,
    poi text not null
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


-- name: get_journey^
select
    *
from
    journey
where
    id = :journey_id;


-- name: add_waypoints*!
insert into
    waypoint (journey_id, lat, lon, cum_dist)
values
    (:journey_id, :lat, :lon, :cum_dist);


-- name: waypoints_for_journey
select
    *
from
    waypoint
where
    journey_id = :journey_id;


-- name: get_waypoint_for_distance^
select
    *,
    (
        select
            cum_dist
        from
            waypoint
        where
            journey_id = :journey_id
        order by
            cum_dist desc
        fetch first
            row only
    ) as journey_distance
from
    waypoint
where
    journey_id = :journey_id
    and :distance > cum_dist
order by
    cum_dist desc
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
        img_url,
        map_url,
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
        :img_url,
        :map_url,
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


-- name: add_steps*!
insert into
    step (journey_id, gargling_id, taken_at, amount)
values
    (
        :journey_id,
        (
            select
                id
            from
                gargling
            where
                first_name = :first_name
        ),
        :taken_at,
        :amount
    );
