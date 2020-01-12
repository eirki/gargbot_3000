-- name: create_schema#
create table congrats (sentence text);


--name: add_congrats*!
insert into
    congrats (sentence)
values
    (:sentence);


-- name: get_congrats
select
    slack_nick,
    slack_id,
    extract(
        year
        from
            bday
    ) :: int as year
from
    user_ids
where
    extract(
        month
        from
            bday
    ) = :month
    and extract(
        day
        from
            bday
    ) = :day;


-- name: get_sentence^
select
    sentence
from
    congrats
order by
    random()
limit
    1;
