-- name: migrations#
create table withings_tokens (
    id int not null unique primary key,
    access_token text not null,
    refresh_token text not null,
    expires_at int not null,
    enable_report boolean not null default false
);


alter table
    fitbit_tokens rename column fitbit_id to id;


alter table
    fitbit_tokens
add
    column enable_report boolean not null default false;


update
    fitbit_tokens
set
    enable_report = true
from
    health_report
where
    health_report.fitbit_id = fitbit_tokens.id;


drop table health_report;


alter table
    user_ids
add
    column withings_id integer;
