-- name: create_schema#
create table user_ids (
  db_id smallint not null primary key,
  slack_id text,
  slack_nick text,
  first_name text,
  bday date not null,
  avatar text,
  slack_avatar text,
  fitbit_id text unique,
  withings_id int unique
);


--name: add_users*!
insert into
  user_ids (
    db_id,
    slack_id,
    slack_nick,
    first_name,
    bday,
    avatar
  )
values
  (
    :db_id,
    :slack_id,
    :slack_nick,
    :first_name,
    :bday,
    :avatar
  );


insert into
  faces (db_id, name)
values
  (:db_id, :first_name);


-- name: random_first_name^
select
  first_name
from
  user_ids
order by
  random()
limit
  1;


-- name: avatar_for_slack_id^
select
  slack_avatar
from
  user_ids
where
  slack_id = :slack_id;
