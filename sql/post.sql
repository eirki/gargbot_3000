-- name: create_schema#
create table post (
    id serial primary key,
    gargling_id smallint not null references gargling(id),
    posted_at timestamp not null,
    content text not null,
    bbcode_uid text not null
);


-- name: add_posts*!
insert into
    post (
        id,
        gargling_id,
        posted_at,
        content,
        bbcode_uid
    )
values
    (
        :id,
        :gargling_id,
        :posted_at,
        :content,
        :bbcode_uid
    );


-- name: random_post^
select
    post.content,
    post.posted_at,
    post.id,
    post.bbcode_uid,
    gargling.slack_nick,
    gargling.avatar
from
    (
        select
            *
        from
            post
        order by
            random()
        limit
            1
    ) as post
    inner join gargling on post.gargling_id = gargling.id;


-- name: post_for_user^
select
    post.content,
    post.posted_at,
    post.id,
    post.bbcode_uid,
    gargling.slack_nick,
    gargling.avatar
from
    post as post
    inner join gargling on post.gargling_id = gargling.id
where
    gargling.slack_nick = :slack_nick
order by
    random()
limit
    1;
