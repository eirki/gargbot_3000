-- name: create_schema#
create table post (
    id serial primary key,
    gargling_id smallint not null references gargling(id),
    post_timestamp timestamp not null,
    content text not null,
    bbcode_uid text not null
);


-- name: add_posts*!
insert into
    post (
        gargling_id,
        id,
        post_timestamp,
        content,
        bbcode_uid
    )
values
    (
        :gargling_id,
        :id,
        :post_timestamp,
        :content,
        :bbcode_uid
    );


-- name: random_post^
select
    post.gargling_id,
    post.content,
    post.post_timestamp,
    post.id,
    post.bbcode_uid,
    user_ids.slack_nick,
    user_ids.avatar
from
    (
        select
            *
        from
            post
        where
            gargling_id in (2, 3, 5, 6, 7, 9, 10, 11)
        order by
            random()
        limit
            1
    ) as post
    inner join user_ids on post.gargling_id = user_ids.gargling_id;


-- name: post_for_user^
select
    post.gargling_id,
    post.content,
    post.post_timestamp,
    post.id,
    post.bbcode_uid,
    user_ids.slack_nick,
    user_ids.avatar
from
    post as post
    inner join user_ids on post.gargling_id = user_ids.gargling_id
where
    user_ids.slack_nick = :slack_nick
order by
    random()
limit
    1;
