DROP TABLE IF EXISTS phpbb_posts;

CREATE TABLE phpbb_posts (
    post_id SERIAL PRIMARY KEY,
    db_id SMALLINT NOT NULL,
    post_timestamp TIMESTAMP NOT NULL,
    post_text TEXT NOT NULL,
    bbcode_uid VARCHAR(8) NOT NULL
);

CREATE INDEX db_idx ON phpbb_posts (db_id);
