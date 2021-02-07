-- name: migrations#
alter table
    fitbit_token_gargling rename constraint fitbit_token_gargling_fitbit_id_fkey to fitbit_token_gargling_service_user_id_fkey;


alter table
    googlefit_token_gargling rename constraint googlefit_token_gargling_googlefit_id_fkey to googlefit_token_gargling_service_user_id_fkey;


alter table
    polar_token_gargling rename constraint polar_token_gargling_polar_id_fkey to polar_token_gargling_service_user_id_fkey;


alter table
    withings_token_gargling rename constraint withings_token_gargling_withings_id_fkey to withings_token_gargling_service_user_id_fkey;


alter table
    gargling
add
    column last_sync_reminder_ts text;


alter table
    gargling
add
    column sync_reminder_is_enabled boolean not null default true;


alter table
    googlefit_token
alter column
    enable_steps
set
    not null;



alter table
    polar_token
alter column
    enable_steps
set
    not null;

