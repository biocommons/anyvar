DROP DATABASE IF EXISTS anyvar;
DROP USER IF EXISTS anyvar;

CREATE USER anyvar WITH PASSWORD 'anyvar-pw';
CREATE DATABASE anyvar WITH OWNER anyvar;
