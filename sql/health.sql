-- name: create_schema#
create table fitbit_tokens (
  fitbit_id text not null unique primary key,
  access_token text not null,
  refresh_token text not null,
  expires_at float8 not null
);


create table health_report (fitbit_id text not null primary key);


-- name: persist_token!
insert into
  fitbit_tokens (
    fitbit_id,
    access_token,
    refresh_token,
    expires_at
  )
values
  (
    :user_id,
    :access_token,
    :refresh_token,
    :expires_at
  ) on conflict (fitbit_id) do
update
set
  (access_token, refresh_token, expires_at) = (
    excluded.access_token,
    excluded.refresh_token,
    excluded.expires_at
  );


--name: enable_daily_report!
insert into
  health_report (fitbit_id)
values
  (:fitbit_id);


--name: disable_daily_report!
delete from
  health_report
where
  fitbit_id = :fitbit_id;


-- name: match_ids!
update
  gargling
set
  fitbit_id = null
where
  fitbit_id = :fitbit_id;


update
  gargling
set
  fitbit_id = :fitbit_id
where
  id = :id;


-- name: is_id_matched^
select
  true
from
  gargling
where
  fitbit_id = :fitbit_id;


-- name: all_fitbit_tokens
select
  fitbit_tokens.fitbit_id,
  fitbit_tokens.access_token,
  fitbit_tokens.refresh_token,
  fitbit_tokens.expires_at,
  gargling.slack_nick
from
  fitbit_tokens
  inner join gargling on fitbit_tokens.fitbit_id = gargling.fitbit_id;


-- name: fitbit_tokens_for_slack_nicks
select
  fitbit_tokens.fitbit_id,
  fitbit_tokens.access_token,
  fitbit_tokens.refresh_token,
  fitbit_tokens.expires_at,
  gargling.slack_nick
from
  fitbit_tokens
  inner join gargling on fitbit_tokens.fitbit_id = gargling.fitbit_id
where
  gargling.slack_nick = any(:slack_nicks);


-- name: daily_report_tokens
select
  fitbit_tokens.fitbit_id,
  fitbit_tokens.access_token,
  fitbit_tokens.refresh_token,
  fitbit_tokens.expires_at,
  gargling.slack_nick
from
  fitbit_tokens
  inner join gargling on fitbit_tokens.fitbit_id = gargling.fitbit_id
  inner join health_report on fitbit_tokens.fitbit_id = health_report.fitbit_id;


-- name: is_fitbit_user^
select
  true
from
  fitbit_tokens
where
  fitbit_id = :fitbit_id;


-- name: all_ids_nicks
select
  id,
  slack_nick
from
  gargling;


--name: parse_nicks_from_args
select
  slack_nick
from
  gargling
where
  slack_nick = any(:args);
