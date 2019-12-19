-- name: create_schema#
create table msn_messages (
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
    msn_messages (
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
