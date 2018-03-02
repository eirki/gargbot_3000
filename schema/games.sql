DROP TABLE IF EXISTS games;
CREATE TABLE games (
game_id mediumint(8) unsigned NOT NULL PRIMARY KEY AUTO_INCREMENT,
name CHAR(50),
color CHAR(6)
);
ALTER TABLE games ADD color CHAR(6) AFTER name;

DROP TABLE IF EXISTS games_votes;
CREATE TABLE games_votes (
game_id mediumint(8) ,
slack_id CHAR(9)
);
ALTER TABLE games_votes ADD CONSTRAINT UNIQUE (game_id, slack_id);

DROP TABLE IF EXISTS games_stars;
CREATE TABLE games_stars (
game_id mediumint(8) ,
slack_id CHAR(9)
);
ALTER TABLE games_stars ADD CONSTRAINT UNIQUE (game_id, slack_id);


