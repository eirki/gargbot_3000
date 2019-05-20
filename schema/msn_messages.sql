DROP TABLE IF EXISTS msn_messages;

CREATE TABLE msn_messages (
	session_id TEXT,
	msg_type TEXT,
	msg_time TIMESTAMP(3),
	msg_source TEXT,
	msg_color TEXT,
	from_user TEXT,
	to_users TEXT,
	msg_text TEXT,
	db_id SMALLINT NOT NULL
);
