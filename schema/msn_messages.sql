DROP TABLE IF EXISTS msn_messages;
CREATE TABLE msn_messages (
session_ID CHAR(50),
msg_type CHAR(10),
msg_time DATETIME(3),
msg_source CHAR(10),
msg_color CHAR(10),
from_user CHAR(200),
to_users TEXT,
msg_text TEXT);

ALTER TABLE msn_messages ADD db_id mediumint(8) unsigned NOT NULL;
