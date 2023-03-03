#!/bin/bash

if [ -z "$UTA_VERSION" ]; then
    export UTA_VERSION=uta_20210129
fi

# TODO think about auth
# if [ -z "$UTA_ADMIN_PASSWORD" ]; then
#     echo "Must provide nonempty env var UTA_ADMIN_PASSWORD"
#     exit 1
# fi

psql -U uta_admin -d uta -c "SELECT COUNT(*) FROM information_schema.role_table_grants WHERE grantee = 'PUBLIC' AND table_name = 'tx_similarity_v';"
CHECK=$?

set -xeo pipefail

if [ $CHECK -ne 0 ]; then
    createuser -U postgres uta_admin
    createuser -U postgres anonymous
    createdb -U postgres -O uta_admin uta
    psql -U postgres -c "ALTER USER uta_admin WITH PASSWORD '$UTA_ADMIN_PASSWORD'"

    curl -s "http://dl.biocommons.org/uta/${UTA_VERSION}.pgd.gz" \
        | gzip -cdq  \
        | grep -v "^REFRESH MATERIALIZED VIEW" \
        | psql -U uta_admin -d uta --echo-errors --single-transaction -v ON_ERROR_STOP=1
fi
