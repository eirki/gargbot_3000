-- name: create_schema#
create table message (
    session_id text,
    sent_at timestamp(3),
    source text,
    color text,
    from_user text,
    to_users text,
    content text,
    gargling_id smallint references gargling(id)
);


--name: add_messages*!
insert into
    message (
        session_id,
        sent_at,
        color,
        from_user,
        content,
        gargling_id
    )
values
    (
        :session_id,
        :sent_at,
        :color,
        :from_user,
        :content,
        :gargling_id
    );


-- name: random_message_session
select
    sent_at,
    from_user,
    content,
    color,
    gargling_id
from
    message
where
    session_id = (
        select
            session_id
        from
            message
        order by
            random()
        limit
            1
    )
order by
    sent_at;


-- name: message_session_for_user_id
with session as (
    select
        message.session_id,
        message.gargling_id
    from
        message
        inner join gargling on message.gargling_id = gargling.id
    where
        gargling.slack_nick = :slack_nick
    order by
        random()
    limit
        1
)
select
    sent_at,
    from_user,
    content,
    color,
    gargling_id,
    case
        when gargling_id = (
            select
                gargling_id
            from
                session
        ) then TRUE
        else FALSE
    end as is_user
from
    message
where
    message.session_id = (
        select
            session_id
        from
            session
    )
order by
    sent_at;
