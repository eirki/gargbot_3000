-- name: migrations#
alter table
    user_ids rename to gargling;


alter table
    gargling rename column db_id to id;


alter table
    gargling rename column bday to birthday;


alter table
    dbx_pictures rename to picture;


alter table
    picture rename column pic_id to id;


alter table
    picture rename column taken to taken_at;


alter table
    dbx_pictures_faces rename to picture_gargling;


alter table
    picture_gargling rename column db_id to gargling_id;


alter table
    picture_gargling rename column pic_id to picture_id;


alter table
    fitbit_tokens rename to fitbit_token;


alter table
    msn_messages rename to message;


alter table
    message rename column db_id to gargling_id;


alter table
    message rename column msg_time to sent_at;


alter table
    message rename column msg_color to color;


alter table
    message rename column msg_source to source;


alter table
    message rename column msg_text to content;


alter table
    phpbb_posts rename to post;


alter table
    post rename column post_id to id;


alter table
    post rename column db_id to gargling_id;


alter table
    post rename column post_timestamp to posted_at;


alter table
    post rename column post_text to content;


alter table
    withings_tokens rename to withings_token;


create table fitbit_token_gargling (
    fitbit_id text not null references fitbit_token(id),
    gargling_id smallint not null references gargling(id)
);


create table withings_token_gargling (
    withings_id smallint not null references withings_token(id),
    gargling_id smallint not null references gargling(id)
);


drop table faces;


alter table
    gargling drop column fitbit_id;


alter table
    gargling drop column withings_id;


alter table
    message drop column msg_type;


alter table
    post drop column post_time;


alter table
    picture_gargling
alter column
    gargling_id
set
    not null;


alter table
    picture_gargling
alter column
    picture_id
set
    not null;


alter table
    message
alter column
    gargling_id drop not null;


update
    message
set
    gargling_id = 5
where
    gargling_id = 0
    and from_user = any(
        array ['eirkk',
'gople - how is your life today?',
'slam shuffle!',
'patience_sticky',
'(explode!)',
'blap!']
    );


update
    message
set
    gargling_id = null
where
    gargling_id = 0;


alter table
    post
alter column
    posted_at
set
    not null;


delete from
    post
where
    gargling_id not in (2, 3, 5, 6, 7, 9, 10, 11);


alter table
    message
add
    constraint message_gargling_id_fkey foreign key (gargling_id) references gargling(id);


alter table
    picture_gargling
add
    constraint picture_gargling_gargling_id_fkey foreign key (gargling_id) references gargling(id);


alter table
    picture_gargling
add
    constraint picture_gargling_picture_id_fkey foreign key (picture_id) references picture(id);


alter table
    post
add
    constraint post_gargling_id_fkey foreign key (gargling_id) references gargling(id);


alter index dbx_pictures_pkey rename to picture_pkey;


alter index fitbit_tokens_pkey rename to fitbit_token_pkey;


alter index phpbb_posts_pkey rename to post_pkey;


alter index user_ids_pkey rename to gargling_pkey;


alter index withings_tokens_pkey rename to withings_token_pkey;


alter sequence dbx_pictures_pic_id_seq rename to picture_id_seq;


alter sequence phpbb_posts_post_id_seq rename to post_id_seq;


drop index if exists db_idx;
