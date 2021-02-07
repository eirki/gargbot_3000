-- name: create_schema#
create table fitbit_token (
  id text not null unique primary key,
  access_token text not null,
  refresh_token text not null,
  expires_at float not null,
  enable_steps boolean not null default false,
  enable_weight boolean not null default false
);


create table withings_token (
  id int not null unique primary key,
  access_token text not null,
  refresh_token text not null,
  expires_at int not null,
  enable_steps boolean not null default false,
  enable_weight boolean not null default false
);


create table polar_token (
  id int not null unique primary key,
  access_token text not null,
  refresh_token text default null,
  expires_at int default null,
  enable_steps boolean not null default false,
  enable_weight boolean not null default false
);


create table googlefit_token (
  id serial primary key,
  access_token text not null,
  refresh_token text,
  expires_at int not null,
  enable_steps boolean not null default false,
  enable_weight boolean not null default false
);


create table fitbit_token_gargling (
  service_user_id text not null references fitbit_token(id),
  gargling_id smallint not null references gargling(id)
);


create table withings_token_gargling (
  service_user_id int not null references withings_token(id),
  gargling_id smallint not null references gargling(id)
);


create table polar_token_gargling (
  service_user_id int not null references polar_token(id),
  gargling_id smallint not null references gargling(id)
);


create table googlefit_token_gargling (
  service_user_id int not null references googlefit_token(id),
  gargling_id smallint not null references gargling(id)
);


create table cached_step (
  gargling_id smallint not null references gargling(id),
  n_steps int not null,
  created_at timestamp not null,
  taken_at date not null
);


create unique index on cached_step (gargling_id, taken_at);


-- name: persist_token!
insert into
  {token_table}
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


-- name: insert_googlefit_token<!
insert into
  googlefit_token (
    access_token,
    refresh_token,
    expires_at
  )
values
  (
    :access_token,
    :refresh_token,
    :expires_at
  ) returning id;


-- name: update_googlefit_token!
update
  googlefit_token
set
  access_token = :access_token,
  refresh_token = :refresh_token,
  expires_at = :expires_at
where
  id = :id;


--name: disable_services!
update
  fitbit_token
set
  {type_col} = false
from
  fitbit_token_gargling
where
  fitbit_token.id = fitbit_token_gargling.service_user_id
  and fitbit_token_gargling.gargling_id = :gargling_id;


update
  withings_token
set
  {type_col} = false
from
  withings_token_gargling
where
  withings_token.id = withings_token_gargling.service_user_id
  and withings_token_gargling.gargling_id = :gargling_id;


update
  polar_token
set
  {type_col} = false
from
  polar_token_gargling
where
  polar_token.id = polar_token_gargling.service_user_id
  and polar_token_gargling.gargling_id = :gargling_id;


update
  googlefit_token
set
  {type_col} = false
from
  googlefit_token_gargling
where
  googlefit_token.id = googlefit_token_gargling.service_user_id
  and googlefit_token_gargling.gargling_id = :gargling_id;


--name: toggle_service!
update
  {token_table}
set
  {type_col} = :enable_
from
  {token_gargling_table}
where
  {token_table}.id = {token_gargling_table}.service_user_id
  and {token_gargling_table}.gargling_id = :gargling_id;


-- name: match_ids!
delete from
  {token_gargling_table}

where
  gargling_id = :gargling_id;


insert into
  {token_gargling_table}

  (
    service_user_id
,
    gargling_id
  )
values
  (:service_user_id, :gargling_id);


-- name: service_user_id_for_gargling_id^
select
 service_user_id
from
  {token_gargling_table}

where
  gargling_id = :gargling_id;


-- name: is_registered^
select
   true as is_registered
from
   {token_table}
  inner join
  {token_gargling_table}
  on {token_table}.id = {token_gargling_table}.service_user_id
where
  {token_gargling_table}.gargling_id = :gargling_id;


-- name: tokens
select
  gargling.id as gargling_id,
  gargling.first_name,
  fitbit.id as service_user_id,
  fitbit.access_token,
  fitbit.refresh_token,
  fitbit.expires_at,
  fitbit.enable_steps,
  fitbit.enable_weight,
  'fitbit' as service
from
  fitbit_token as fitbit
  inner join fitbit_token_gargling on fitbit.id = fitbit_token_gargling.service_user_id
  inner join gargling on fitbit_token_gargling.gargling_id = gargling.id
union
all
select
  gargling.id as gargling_id,
  gargling.first_name,
  withings.id :: text as service_user_id,
  withings.access_token,
  withings.refresh_token,
  withings.expires_at :: float,
  withings.enable_steps,
  withings.enable_weight,
  'withings' as service
from
  withings_token as withings
  inner join withings_token_gargling on withings.id = withings_token_gargling.service_user_id
  inner join gargling on withings_token_gargling.gargling_id = gargling.id
union
all
select
  gargling.id as gargling_id,
  gargling.first_name,
  polar.id :: text as service_user_id,
  polar.access_token,
  polar.refresh_token,
  polar.expires_at,
  polar.enable_steps,
  polar.enable_weight,
  'polar' as service
from
  polar_token as polar
  inner join polar_token_gargling on polar.id = polar_token_gargling.service_user_id
  inner join gargling on polar_token_gargling.gargling_id = gargling.id
union
all
select
  gargling.id as gargling_id,
  gargling.first_name,
  googlefit.id :: text as service_user_id,
  googlefit.access_token,
  googlefit.refresh_token,
  googlefit.expires_at,
  googlefit.enable_steps,
  googlefit.enable_weight,
  'googlefit' as service
from
  googlefit_token as googlefit
  inner join googlefit_token_gargling on googlefit.id = googlefit_token_gargling.service_user_id
  inner join gargling on googlefit_token_gargling.gargling_id = gargling.id


-- name: all_ids_nicks
select
  id,
  slack_nick
from
  gargling;


-- name: upsert_steps*!
insert into
  cached_step (gargling_id, n_steps, created_at, taken_at)
values
  (:gargling_id, :n_steps, :created_at, :taken_at) on conflict (gargling_id, taken_at) do
update
set
  n_steps = case
    when excluded.created_at > cached_step.created_at then excluded.n_steps
    else cached_step.n_steps
  end;


-- name: cached_step_for_date^
select
  n_steps
from
  cached_step
where
  taken_at = :date
  and gargling_id = :id;


-- name: health_status
select
  'fitbit' as service,
  enable_steps,
  enable_weight
from
  fitbit_token as fitbit
  inner join fitbit_token_gargling on fitbit.id = fitbit_token_gargling.service_user_id
  inner join gargling on fitbit_token_gargling.gargling_id = gargling.id
where
  gargling_id = :gargling_id
union
all
select
  'withings' as service,
  enable_steps,
  enable_weight
from
  withings_token as withings
  inner join withings_token_gargling on withings.id = withings_token_gargling.service_user_id
  inner join gargling on withings_token_gargling.gargling_id = gargling.id
where
  gargling_id = :gargling_id
union
all
select
  'polar' as service,
  enable_steps,
  enable_weight
from
  polar_token as polar
  inner join polar_token_gargling on polar.id = polar_token_gargling.service_user_id
  inner join gargling on polar_token_gargling.gargling_id = gargling.id
where
  gargling_id = :gargling_id
union
all
select
  'googlefit' as service,
  enable_steps,
  enable_weight
from
  googlefit_token as googlefit
  inner join googlefit_token_gargling on googlefit.id = googlefit_token_gargling.service_user_id
  inner join gargling on googlefit_token_gargling.gargling_id = gargling.id
where
  gargling_id = :gargling_id;


-- name: get_sync_reminder_users
select
  id,
  slack_id,
  last_sync_reminder_ts
from
  gargling
where
  sync_reminder_is_enabled;


-- name: update_reminder_ts!
update
  gargling
set
  last_sync_reminder_ts = :ts
where
  id = :id;


-- name: toggle_sync_reminding!
update
  gargling
set
  sync_reminder_is_enabled = :enable_
where
  id = :id;

