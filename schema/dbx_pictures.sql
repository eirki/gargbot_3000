-- name: create_schema#
create table dbx_pictures (
    path text,
    topic text,
    taken timestamp,
    pic_id serial primary key
);


create table faces (
    db_id smallint not null primary key,
    name text
);


create table dbx_pictures_faces (db_id smallint, pic_id smallint);


--name: add_picture<!
insert into
    dbx_pictures (path, topic, taken)
values
    (:path, :topic, :taken) returning pic_id;


--name: add_faces*!
insert into
    dbx_pictures_faces (db_id, pic_id)
values
    (:db_id, :pic_id);


--name: define_args#
create materialized view if not exists picture_year as
select
    distinct extract(
        year
        from
            taken
    ) :: text as year
from
    dbx_pictures
order by
    year;


create materialized view if not exists picture_topic as
select
    distinct topic
from
    dbx_pictures;


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
                    user_ids
            )
    ) as users;


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
                    array [db_id :: text, slack_nick]
                from
                    user_ids
                where
                    slack_nick = any(:args)
            ) as users
    );


-- name: random_pic^
select
    path,
    taken
from
    dbx_pictures
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


-- name: pic_for_topic_year_users^
select
    picture.path,
    picture.taken
from
    dbx_pictures as picture
    /*{% if users|length == 1 %}*/
    left join dbx_pictures_faces as face on picture.pic_id = face.pic_id
    /*{% elif users|length > 1 %}*/
    left join (
        select
            array_agg(db_id) as db_ids,
            pic_id
        from
            dbx_pictures_faces
        group by
            pic_id
    ) as face on picture.pic_id = face.pic_id
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
            picture.taken
    ) = :year
    /*{% endif %}*/
    /*{% if users|length == 1 %}*/
    /*{{ and() }}*/
    face.db_id = (:users) [1] [1] :: smallint
    /*{% elif users|length > 1 %}*/
    /*{% for db_id, slack_nick in users %}*/
    /*{{ and() }}*/
    /*{{ db_id }}*/
    :: smallint = any(face.db_ids)
    /*{% endfor %}*/
    /*{% endif %}*/
order by
    random()
limit
    1
