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


-- name: match_ids!
update
  user_ids
set
  fitbit_id = null
where
  fitbit_id = :fitbit_id;


update
  user_ids
set
  fitbit_id = :fitbit_id
where
  db_id = :db_id;


-- name: get_all_fitbit_tokens
select
  t.fitbit_id as fitbit_id,
  t.access_token as access_token,
  t.refresh_token as refresh_token,
  t.expires_at as expires_at,
  u.slack_nick as slack_nick
from
  fitbit_tokens t
  inner join user_ids u on t.fitbit_id = u.fitbit_id;


-- name: get_fitbit_tokens_by_slack_nicks
select
  t.fitbit_id as fitbit_id,
  t.access_token as access_token,
  t.refresh_token as refresh_token,
  t.expires_at as expires_at,
  u.slack_nick as slack_nick
from
  fitbit_tokens t
  inner join user_ids u on t.fitbit_id = u.fitbit_id
where
  u.slack_nick = ANY(:slack_nicks);


-- name: get_daily_report_tokens
select
  t.fitbit_id as fitbit_id,
  t.access_token as access_token,
  t.refresh_token as refresh_token,
  t.expires_at as expires_at,
  u.slack_nick as slack_nick
from
  fitbit_tokens t
  inner join user_ids u on t.fitbit_id = u.fitbit_id
  inner join health_report h on t.fitbit_id = h.fitbit_id;


-- name: is_fitbit_user^
select
  true
from
  fitbit_tokens
where
  fitbit_id = :fitbit_id;


-- name: get_nicks_ids
SELECT
  db_id,
  slack_nick
FROM
  user_ids;


--name: parse_nicks_from_args
SELECT
  slack_nick
FROM
  user_ids
where
  slack_nick = ANY(:args);
