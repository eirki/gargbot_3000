-- name: create_schema#
create table phpbb_posts (
    post_id serial primary key,
    db_id smallint not null,
    post_timestamp timestamp not null,
    post_text text not null,
    bbcode_uid text not null
);


create index db_idx on phpbb_posts (db_id);


--name: add_posts*!
INSERT INTO
    phpbb_posts (
        db_id,
        post_id,
        post_timestamp,
        post_text,
        bbcode_uid
    )
VALUES
    (
        :db_id,
        :post_id,
        :post_timestamp,
        :post_text,
        :bbcode_uid
    );
