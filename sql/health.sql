-- name: create_schema#
create table fitbit_token (
  id text not null unique primary key,
  access_token text not null,
  refresh_token text not null,
  expires_at float not null,
  enable_report boolean not null default false
);


create table withings_token (
  id int not null unique primary key,
  access_token text not null,
  refresh_token text not null,
  expires_at int not null,
  enable_report boolean not null default false
);


create table polar_token (
  id int not null unique primary key,
  access_token text not null,
  refresh_token text default null,
  expires_at int default null,
  enable_report boolean default false
);


create table googlefit_token (
  id serial primary key,
  access_token text not null,
  refresh_token text,
  expires_at int not null,
  enable_report boolean default false
);


create table fitbit_token_gargling (
  fitbit_id text not null references fitbit_token(id),
  gargling_id smallint not null references gargling(id)
);


create table withings_token_gargling (
  withings_id int not null references withings_token(id),
  gargling_id smallint not null references gargling(id)
);


create table polar_token_gargling (
  polar_id int not null references polar_token(id),
  gargling_id smallint not null references gargling(id)
);


create table googlefit_token_gargling (
  googlefit_id int not null references googlefit_token(id),
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
  /*{{ {
   "fitbit": "fitbit_token",
   "withings": "withings_token",
   "polar": "polar_token",
   }[service] }}*/
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


--name: toggle_report!
update
  /*{{ {
   "fitbit": "fitbit_token",
   "withings": "withings_token",
   "polar": "polar_token",
   "googlefit": "googlefit_token",
   }[service] }}*/
  as service_token
set
  enable_report = :enable_
from
  /*{{ {
   "fitbit": "fitbit_token_gargling",
   "withings": "withings_token_gargling",
   "polar": "polar_token_gargling",
   "googlefit": "googlefit_token_gargling",
   }[service] }}*/
  as service_token_gargling
where
  service_token.id = service_token_gargling.
  /*{{ {
   "fitbit": "fitbit_id",
   "withings": "withings_id",
   "polar": "polar_id",
   "googlefit": "googlefit_id",
   }[service] }}*/
  and service_token_gargling.gargling_id = :gargling_id;


-- name: match_ids!
delete from
  /*{{ {
   "fitbit": "fitbit_token_gargling",
   "withings": "withings_token_gargling",
   "polar": "polar_token_gargling",
   "googlefit": "googlefit_token_gargling",
   }[service] }}*/
where
  gargling_id = :gargling_id;


insert into
  /*{{ {
   "fitbit": "fitbit_token_gargling",
   "withings": "withings_token_gargling",
   "polar": "polar_token_gargling",
   "googlefit": "googlefit_token_gargling"
   }[service] }}*/
  (
    /*{{ {
     "fitbit": "fitbit_id",
     "withings": "withings_id",
     "polar": "polar_id",
     "googlefit": "googlefit_id",
     }[service] }}*/
,
    gargling_id
  )
values
  (:service_user_id, :gargling_id);


-- name: service_user_id_for_gargling_id^
select
  /*{{ {
   "fitbit": "fitbit_id",
   "withings": "withings_id",
   "polar": "polar_id",
   "googlefit": "googlefit_id",
   }[service] }}*/
  as service_user_id
from
  /*{{ {
   "fitbit": "fitbit_token_gargling",
   "withings": "withings_token_gargling",
   "polar": "polar_token_gargling",
   "googlefit": "googlefit_token_gargling",
   }[service] }}*/
where
  gargling_id = :gargling_id;


-- name: is_registered^
select
  service_token.enable_report
from
  /*{{ {
   "fitbit": "fitbit_token",
   "withings": "withings_token",
   "polar": "polar_token",
   "googlefit": "googlefit_token",
   }[service] }}*/
  as service_token
  inner join
  /*{{ {
   "fitbit": "fitbit_token_gargling",
   "withings": "withings_token_gargling",
   "polar": "polar_token_gargling",
   "googlefit": "googlefit_token_gargling",
   }[service] }}*/
  as service_token_gargling on service_token.id = service_token_gargling.
  /*{{ {
   "fitbit": "fitbit_id",
   "withings": "withings_id",
   "polar": "polar_id",
   "googlefit": "googlefit_id",
   }[service] }}*/
where
  service_token_gargling.gargling_id = :gargling_id;


-- name: tokens
select
  gargling.id as gargling_id,
  gargling.first_name,
  fitbit.id as service_user_id,
  fitbit.access_token,
  fitbit.refresh_token,
  fitbit.expires_at,
  'fitbit' as service
from
  fitbit_token as fitbit
  inner join fitbit_token_gargling on fitbit.id = fitbit_token_gargling.fitbit_id
  inner join gargling on fitbit_token_gargling.gargling_id = gargling.id
where
  fitbit.enable_report
union
all
select
  gargling.id as gargling_id,
  gargling.first_name,
  withings.id :: text as service_user_id,
  withings.access_token,
  withings.refresh_token,
  withings.expires_at :: float,
  'withings' as service
from
  withings_token as withings
  inner join withings_token_gargling on withings.id = withings_token_gargling.withings_id
  inner join gargling on withings_token_gargling.gargling_id = gargling.id
where
  withings.enable_report
union
all
select
  gargling.id as gargling_id,
  gargling.first_name,
  polar.id :: text as service_user_id,
  polar.access_token,
  polar.refresh_token,
  polar.expires_at,
  'polar' as service
from
  polar_token as polar
  inner join polar_token_gargling on polar.id = polar_token_gargling.polar_id
  inner join gargling on polar_token_gargling.gargling_id = gargling.id
where
  polar.enable_report
union
all
select
  gargling.id as gargling_id,
  gargling.first_name,
  googlefit.id :: text as service_user_id,
  googlefit.access_token,
  googlefit.refresh_token,
  googlefit.expires_at,
  'googlefit' as service
from
  googlefit_token as googlefit
  inner join googlefit_token_gargling on googlefit.id = googlefit_token_gargling.googlefit_id
  inner join gargling on googlefit_token_gargling.gargling_id = gargling.id
where
  googlefit.enable_report;


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
