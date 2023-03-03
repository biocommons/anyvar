# Lightweight docker image that just adds some a script that configures and populates UTA data into postgres
# To make the data persistent, mount a volume to /var/lib/postgres/data
# The setup script notes that it already ran by writing a initialized.txt file there

FROM postgres:15.1

RUN apt-get update && apt-get install -y --no-install-recommends curl

COPY uta_setup.sh /docker-entrypoint-initdb.d/uta_setup.sh
RUN chmod +x /docker-entrypoint-initdb.d/uta_setup.sh
