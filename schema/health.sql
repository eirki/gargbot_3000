DROP TABLE IF EXISTS fitbit;

CREATE TABLE fitbit (
    fitbit_id TEXT NOT NULL UNIQUE,
    access_token TEXT NOT NULL,
    refresh_token TEXT NOT NULL,
    expires_at float8 NOT NULL,
    db_id SMALLINT
);

CREATE TABLE health_report (
    db_id SMALLINT NOT NULL
);
