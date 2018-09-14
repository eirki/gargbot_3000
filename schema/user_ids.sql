DROP TABLE IF EXISTS user_ids;

CREATE TABLE user_ids (
    db_id SMALLINT NOT NULL PRIMARY KEY,
    slack_id VARCHAR(9),
    slack_nick VARCHAR(50),
    first_name VARCHAR(50),
    bday DATE NOT NULL
);
