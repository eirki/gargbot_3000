-- name: create_schema#
create table congrats (sentence text);


--name: add_congrats*!
insert into
    congrats (sentence)
values
    (:sentence);
