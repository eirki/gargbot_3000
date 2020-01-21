-- name: create_schema#
create table gargling (
  id smallint not null primary key,
  slack_id text,
  slack_nick text,
  first_name text,
  birthday date not null,
  avatar text,
  slack_avatar text
);


--name: add_users*!
insert into
  gargling (
    id,
    slack_id,
    slack_nick,
    first_name,
    birthday,
    avatar
  )
values
  (
    :id,
    :slack_id,
    :slack_nick,
    :first_name,
    :birthday,
    :avatar
  );


-- name: random_first_name^
select
  first_name
from
  gargling
order by
  random()
limit
  1;


-- name: avatar_for_slack_id^
select
  slack_avatar
from
  gargling
where
  slack_id = :slack_id;
