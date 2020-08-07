-- name: migrations#
alter table
    location
add
    column traversal_map_url text;


alter table
    waypoint
alter column
    cum_dist
set
    not null;


alter table
    waypoint
alter column
    cum_dist
set
    data type double precision using cum_dist :: double precision;
