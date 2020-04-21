-- name: create_schema#
create table picture (
    id serial primary key,
    path text,
    topic text,
    taken_at timestamp
);


create index picture_ix_path on picture (path);


create index picture_ix_topic on picture (topic);


create index picture_ix_year on picture (
    extract(
        year
        from
            taken_at
    )
);


create table picture_gargling (
    picture_id smallint not null references picture(id),
    gargling_id smallint not null references gargling(id)
);


create index picture_gargling_ix_picture_id on picture_gargling (picture_id);


create index picture_gargling_ix_gargling_id on picture_gargling (gargling_id);


--name: add_picture<!
insert into
    picture (path, topic, taken_at)
values
    (:path, :topic, :taken_at) returning id;


--name: add_faces*!
insert into
    picture_gargling (picture_id, gargling_id)
values
    (:picture_id, :gargling_id);


--name: define_args#
create materialized view if not exists picture_year as
select
    distinct extract(
        year
        from
            taken_at
    ) :: text as year
from
    picture
order by
    year;


create materialized view if not exists picture_topic as
select
    distinct topic
from
    picture;


-- name: get_possible_args^
select
    (
        select
            array(
                select
                    year
                from
                    picture_year
            )
    ) as years,
    (
        select
            array(
                select
                    topic
                from
                    picture_topic
            )
    ) as topics,
    (
        select
            array(
                select
                    slack_nick
                from
                    gargling
            )
    ) as garglings;


-- name: parse_args^
select
    (
        select
            year
        from
            picture_year
        where
            year = any(:args)
    ),
    (
        select
            topic
        from
            picture_topic
        where
            topic = any(:args)
    ),
    (
        select
            array(
                select
                    slack_nick
                from
                    gargling
                where
                    slack_nick = any(:args)
            ) as garglings
    ),
    (
        select
            case
                when 'kun' = any(:args) then true
                else false
            end as exclusive
    );


-- name: random_pic^
select
    path,
    taken_at
from
    picture
where
    topic = (
        select
            topic
        from
            picture_topic
        order by
            random()
        limit
            1
    )
order by
    random()
limit
    1;


-- name: pic_for_topic_year_garglings^
/*{% if garglings | length > 1 or exclusive %}*/
with garglings_arg as (
    select
        array(
            select
                id
            from
                gargling
            where
                slack_nick = any(:garglings)
            order by
                id
        ) as ids
)
/*{% endif %}*/
select
    picture.path,
    picture.taken_at
from
    picture
    /*{% if garglings | length == 1 and not exclusive %}*/
    inner join (
        select
            picture_id
        from
            picture_gargling
        where
            gargling_id = (
                select
                    id
                from
                    gargling
                where
                    slack_nick = any(:garglings)
            )
    ) as picture_gargling on picture.id = picture_gargling.picture_id
    /*{% elif garglings %}*/
    inner join (
        select
            picture_id,
            array_agg(
                picture_gargling.gargling_id
                order by
                    picture_gargling.gargling_id
            ) as gargling_ids
        from
            picture_gargling
        group by
            picture_id
    ) as picture_gargling on picture.id = picture_gargling.picture_id
    /*{% if exclusive %}*/
    inner join garglings_arg on picture_gargling.gargling_ids = garglings_arg.ids
    /*{% else %}*/
    cross join garglings_arg
    /*{% endif %}*/
    /*{% endif %}*/
    /*{% if topic or year or (garglings | length > 1 and not exclusive) %}*/
where
    /*{% set and = joiner(" and ") %}*/
    /*{% if topic %}*/
    /*{{ and() }}*/
    picture.topic = :topic
    /*{% endif %}*/
    /*{% if year %}*/
    /*{{ and() }}*/
    extract(
        year
        from
            picture.taken_at
    ) = :year
    /*{% endif %}*/
    /*{% if garglings | length > 1 and not exclusive %}*/
    /*{{ and() }}*/
    picture_gargling.gargling_ids <@ garglings_arg.ids
    /*{% endif %}*/
    /*{% endif %}*/
order by
    random()
limit
    1;
