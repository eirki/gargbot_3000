-- name: create_schema#
create table phpbb_posts (
    post_id serial primary key,
    db_id smallint not null,
    post_timestamp timestamp not null,
    post_text text not null,
    bbcode_uid text not null
);


create index db_idx on phpbb_posts (db_id);


-- name: add_posts*!
insert into
    phpbb_posts (
        db_id,
        post_id,
        post_timestamp,
        post_text,
        bbcode_uid
    )
values
    (
        :db_id,
        :post_id,
        :post_timestamp,
        :post_text,
        :bbcode_uid
    );


-- name: get_random_post^
select
    post.db_id,
    post.post_text,
    post.post_timestamp,
    post.post_id,
    post.bbcode_uid,
    user_ids.slack_nick,
    user_ids.avatar
from
    (
        select
            *
        from
            phpbb_posts
        where
            db_id in (2, 3, 5, 6, 7, 9, 10, 11)
        order by
            random()
        limit
            1
    ) as post
    inner join user_ids on post.db_id = user_ids.db_id;


-- name: get_random_post_for_user^
select
    post.db_id,
    post.post_text,
    post.post_timestamp,
    post.post_id,
    post.bbcode_uid,
    user_ids.slack_nick,
    user_ids.avatar
from
    phpbb_posts as post
    inner join user_ids on post.db_id = user_ids.db_id
where
    user_ids.slack_nick = :slack_nick
order by
    random()
limit
    1;
