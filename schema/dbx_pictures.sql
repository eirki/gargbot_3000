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
