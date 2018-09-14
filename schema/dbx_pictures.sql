DROP TABLE IF EXISTS dbx_pictures;

CREATE TABLE dbx_pictures (
	path CHAR(100),
	topic CHAR(30),
	taken datetime,
	pic_id INT PRIMARY KEY AUTO_INCREMENT
);

CREATE TABLE faces (
	db_id INT PRIMARY KEY,
	name char(30)
);

CREATE TABLE dbx_pictures_faces (
	db_id INT,
	pic_id INT
);

