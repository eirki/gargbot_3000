-- name: migrations#
update location set country = 'Norway' where date = '2020-7-26';

update location set country = 'Sweden' where date between '2020-7-27' and '2020-8-12';

update location set country = 'Denmark' where date between '2020-8-13' and '2020-8-16';

update location set country = 'Germany' where date between '2020-8-18' and '2020-8-23';

update location set country = 'Poland' where country = 'Polska';

update location set country = 'Poland' where country = 'Polen';

update location set country = 'Ukraine' where country = 'Україна';
