CREATE USER anyvar;
CREATE DATABASE anyvar_db;
GRANT ALL PRIVILEGES ON DATABASE anyvar_db TO anyvar;
CREATE TABLE vrs_objects (id BIGINT primary key, vrs_id text, vrs_object jsonb);