-- name: migrations#
create table cached_step (
  gargling_id smallint not null references gargling(id),
  n_steps int not null,
  taken_at date not null
);


create unique index on cached_step (gargling_id, taken_at);

alter table
    journey
alter column
    finished_at
set
    data type date using finished_at :: date;


alter table
    journey
alter column
    started_at
set
    data type date using started_at :: date;


alter table
    location
alter column
    date
set
    data type date using date :: date;


alter table
    step
alter column
    taken_at
set
    data type date using taken_at :: date;
