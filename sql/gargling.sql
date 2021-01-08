-- name: create_schema#
create table gargling (
  id smallint not null primary key,
  slack_id text,
  slack_nick text,
  first_name text,
  birthday date not null,
  avatar text,
  slack_avatar text,
  color_hex text not null,
  color_name text not null,
  is_admin boolean not null default false
);


--name: add_users*!
insert into
  gargling (
    id,
    slack_id,
    slack_nick,
    first_name,
    birthday,
    avatar,
    color_name,
    color_hex
  )
values
  (
    :id,
    :slack_id,
    :slack_nick,
    :first_name,
    :birthday,
    :avatar,
    :color_name,
    :color_hex
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


-- name: gargling_id_for_slack_id^
select
  id
from
  gargling
where
  slack_id = :slack_id;


-- name: is_admin$
select
  is_admin
from
 gargling
where
  id = :gargling_id;
