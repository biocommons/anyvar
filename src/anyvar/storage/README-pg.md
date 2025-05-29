Run the following commands to set up a postgres database for use with AnyVar:

1. `docker pull postgres`

2. `docker run -d --name anyvar-pg -p 5432:5432 -e POSTGRES_PASSWORD=postgres postgres`

3. `cat src/anyvar/storage/postgres_init.sql | psql -h localhost -U postgres -p 5432`

When asked to enter a password, use `postgres`

<br/>

For testing, replace the code in step 3 with the below:

`cat src/anyvar/storage/postgres_init_test.sql | psql -h localhost -U postgres -p 5432`
