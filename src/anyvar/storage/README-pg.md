* docker pull postgres

* docker run -d --name anyvar-pg -p 5432:5432 -e POSTGRES_PASSWORD=postgres postgres

* cat src/anyvar/storage/postres_init.sql | psql -h localhost -U postgres -p 5432
