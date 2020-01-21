-- name: create_schema#
create table congrats (sentence text);


--name: add_congrats*!
insert into
    congrats (sentence)
values
    (:sentence);


-- name: congrats_for_date
select
    slack_nick,
    slack_id,
    extract(
        year
        from
            birthday
    ) :: int as year
from
    gargling
where
    extract(
        month
        from
            birthday
    ) = :month
    and extract(
        day
        from
            birthday
    ) = :day;


-- name: random_sentence^
select
    sentence
from
    congrats
order by
    random()
limit
    1;
