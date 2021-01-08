-- name: migrations#
alter table
    gargling
add
    column is_admin boolean not null default false;

update
    gargling
set
    is_admin = true
where
    id = 5;
