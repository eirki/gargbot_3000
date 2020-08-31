-- name: migrations#
alter table
    location drop column map_url;

alter table
    location drop column img_url;


alter table
    location drop column traversal_map_url;


alter table
    location
add
    column country text;


alter table
    waypoint rename cum_dist to distance;
