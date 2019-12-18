DROP TABLE IF EXISTS user_ids;
CREATE TABLE user_ids (
  db_id SMALLINT NOT NULL PRIMARY KEY,
  slack_id TEXT,
  slack_nick TEXT,
  first_name TEXT,
  bday DATE NOT NULL,
  avatar TEXT,
  slack_avatar TEXT,
  fitbit_id TEXT UNIQUE
);
