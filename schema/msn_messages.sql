DROP TABLE IF EXISTS msn_messages;

CREATE TABLE msn_messages (
	session_ID VARCHAR(50),
	msg_type VARCHAR(10),
	msg_time TIMESTAMP(3),
	msg_source VARCHAR(10),
	msg_color VARCHAR(10),
	from_user VARCHAR(200),
	to_users TEXT,
	msg_text TEXT,
	db_id SMALLINT NOT NULL
);
