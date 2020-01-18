-- name: create_schema#
create table fitbit_tokens (
  id text not null unique primary key,
  access_token text not null,
  refresh_token text not null,
  expires_at float not null,
  enable_report boolean not null default false
);


create table withings_tokens (
  id int not null unique primary key,
  access_token text not null,
  refresh_token text not null,
  expires_at int not null,
  enable_report boolean not null default false
);


-- name: persist_token!
insert into
  /*{{ {"fitbit": "fitbit_tokens", "withings": "withings_tokens"}[service] }}*/
  (
    id,
    access_token,
    refresh_token,
    expires_at
  )
values
  (
    :id,
    :access_token,
    :refresh_token,
    :expires_at
  ) on conflict (id) do
update
set
  (access_token, refresh_token, expires_at) = (
    excluded.access_token,
    excluded.refresh_token,
    excluded.expires_at
  );


--name: enable_report!
update
  /*{{ {"fitbit": "fitbit_tokens", "withings": "withings_tokens"}[service] }}*/
set
  enable_report = true
where
  id = :id;


--name: disable_report!
update
  /*{{ {"fitbit": "fitbit_tokens", "withings": "withings_tokens"}[service] }}*/
set
  enable_report = false
where
  id = :id;


-- name: match_ids!
update
  user_ids
set
  /*{{"fitbit_id" if service == "fitbit" else "withings_id" }}*/
  = null
where
  /*{{"fitbit_id" if service == "fitbit" else "withings_id" }}*/
  = :service_user_id;


update
  user_ids
set
  /*{{"fitbit_id" if service == "fitbit" else "withings_id" }}*/
  = :service_user_id
where
  db_id = :db_id;


-- name: is_id_matched^
select
  true
from
  user_ids
where
  /*{{"fitbit_id" if service == "fitbit" else "withings_id" }}*/
  = :id;


-- name: tokens
select
  fitbit.id,
  fitbit.access_token,
  fitbit.refresh_token,
  fitbit.expires_at,
  user_ids.slack_nick,
  'fitbit' as service
from
  fitbit_tokens as fitbit
  inner join user_ids on fitbit.id = user_ids.fitbit_id
  /*{% if slack_nicks or only_report %}*/
where
  /*{% endif  %}*/
  /*{% set and = joiner(" and ") %}*/
  /*{% if slack_nicks %}*/
  /*{{ and() }}*/
  user_ids.slack_nick = any(:slack_nicks)
  /*{% endif  %}*/
  /*{% if only_report %}*/
  /*{{ and() }}*/
  fitbit.enable_report
  /*{% endif  %}*/
union
all
select
  withings.id :: text,
  withings.access_token,
  withings.refresh_token,
  withings.expires_at :: float,
  user_ids.slack_nick,
  'withings' as service
from
  withings_tokens as withings
  inner join user_ids on withings.id = user_ids.withings_id
  /*{% if slack_nicks or only_report %}*/
where
  /*{% endif  %}*/
  /*{% set and = joiner(" and ") %}*/
  /*{% if slack_nicks %}*/
  /*{{ and() }}*/
  user_ids.slack_nick = any(:slack_nicks)
  /*{% endif  %}*/
  /*{% if only_report %}*/
  /*{{ and() }}*/
  withings.enable_report
  /*{% endif  %}*/
;


-- name: is_user^
select
  true
from
  /*{{"fitbit_tokens" if service == "fitbit" else "withings_tokens"}}*/
where
  id :: text = :id;


-- name: all_ids_nicks
select
  db_id,
  slack_nick
from
  user_ids;
