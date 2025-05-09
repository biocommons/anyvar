DROP DATABASE IF EXISTS anyvar_test;
DROP USER IF EXISTS anyvar_test;

CREATE USER anyvar_test WITH PASSWORD 'anyvar-test-pw';
CREATE DATABASE anyvar_test WITH OWNER anyvar_test;
