FROM postgres:15.1

RUN apt-get update && apt-get install -y --no-install-recommends curl

COPY pg_setup.sh /docker-entrypoint-initdb.d/pg_setup.sh
RUN chmod +x /docker-entrypoint-initdb.d/pg_setup.sh
