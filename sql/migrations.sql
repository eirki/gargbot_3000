-- name: migrations#
alter table
    fitbit_token_gargling rename column fitbit_id to service_user_id;


alter table
    withings_token_gargling rename column withings_id to service_user_id;


alter table
    polar_token_gargling rename column polar_id to service_user_id;


alter table
    googlefit_token_gargling rename column googlefit_id to service_user_id;


alter table
    fitbit_token rename column enable_report to enable_steps;


alter table
    withings_token rename column enable_report to enable_steps;


alter table
    polar_token rename column enable_report to enable_steps;


alter table
    googlefit_token rename column enable_report to enable_steps;


alter table
    fitbit_token
add
    column enable_weight boolean not null default false;


alter table
    withings_token
add
    column enable_weight boolean not null default false;


alter table
    polar_token
add
    column enable_weight boolean not null default false;


alter table
    googlefit_token
add
    column enable_weight boolean not null default false;
