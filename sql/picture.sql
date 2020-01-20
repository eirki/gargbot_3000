-- name: create_schema#
create table picture (
    id serial primary key,
    path text,
    topic text,
    taken_at timestamp
);


create table picture_gargling (
    picture_id smallint not null references picture(id),
    gargling_id smallint not null references gargling(id)
);


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
                    array [id :: text, slack_nick]
                from
                    gargling
                where
                    slack_nick = any(:args)
            ) as garglings
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
select
    picture.path,
    picture.taken_at
from
    picture
    /*{% if garglings|length == 1 %}*/
    left join picture_gargling on picture.id = picture_gargling.picture_id
    /*{% elif garglings|length > 1 %}*/
    left join (
        select
            array_agg(gargling_id) as gargling_ids,
            picture_id
        from
            picture_gargling
        group by
            picture_id
    ) as picture_gargling on picture.id = picture_gargling.picture_id
    /*{% endif %}*/
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
    /*{% if garglings|length == 1 %}*/
    /*{{ and() }}*/
    picture_gargling.gargling_id = (:garglings) [1] [1] :: smallint
    /*{% elif garglings|length > 1 %}*/
    /*{% for id, slack_nick in garglings %}*/
    /*{{ and() }}*/
    /*{{ id }}*/
    :: smallint = any(picture_gargling.gargling_ids)
    /*{% endfor %}*/
    /*{% endif %}*/
order by
    random()
limit
    1
