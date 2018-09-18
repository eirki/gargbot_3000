DROP TABLE IF EXISTS dbx_pictures;

CREATE TABLE dbx_pictures (
	path VARCHAR(100),
	topic VARCHAR(30),
	taken TIMESTAMP,
	pic_id SERIAL PRIMARY KEY
);

DROP TABLE IF EXISTS faces;

CREATE TABLE faces (
	db_id SMALLINT NOT NULL PRIMARY KEY,
	name VARCHAR(30)
);

DROP TABLE IF EXISTS dbx_pictures_faces;

CREATE TABLE dbx_pictures_faces (
	db_id SMALLINT,
	pic_id SMALLINT
);
