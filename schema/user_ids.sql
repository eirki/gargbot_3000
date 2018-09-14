DROP TABLE IF EXISTS user_ids;

CREATE TABLE user_ids (
	db_id mediumint(8) unsigned NOT NULL PRIMARY KEY,
	slack_id CHAR(9),
	slack_nick CHAR(50),
	first_name CHAR(50),
	bday DATE NOT NULL
);
