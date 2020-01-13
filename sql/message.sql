-- name: create_schema#
create table msn_message (
    session_id text,
    msg_type text,
    msg_time timestamp(3),
    msg_source text,
    msg_color text,
    from_user text,
    to_users text,
    msg_text text,
    db_id smallint not null
);


--name: add_messages*!
insert into
    msn_message (
        session_id,
        msg_time,
        msg_color,
        from_user,
        msg_text,
        db_id
    )
values
    (
        :session_id,
        :msg_time,
        :msg_color,
        :from_user,
        :msg_text,
        :db_id
    );


-- name: random_message_session
select
    msg_time,
    from_user,
    msg_text,
    msg_color,
    db_id
from
    msn_message
where
    session_id = (
        select
            session_id
        from
            msn_message
        order by
            random()
        limit
            1
    )
order by
    msg_time;


-- name: message_session_for_user_id
with session as (
    select
        msg.session_id,
        msg.db_id
    from
        msn_message as msg
        inner join user_ids as usr on msg.db_id = usr.db_id
    where
        usr.slack_nick = :slack_nick
    order by
        random()
    limit
        1
)
select
    msg_time,
    from_user,
    msg_text,
    msg_color,
    db_id,
    case
        when db_id = (
            select
                db_id
            from
                session
        ) then TRUE
        else FALSE
    end as is_user
from
    msn_message
where
    msn_message.session_id = (
        select
            session_id
        from
            session
    )
order by
    msg_time;
