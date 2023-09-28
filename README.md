# AnyVar

*AnyVar* provides Python and REST interfaces to validate, normalize,
generate identifiers, and register biological sequence variation
according to the GA4GH Variation Representation standards.

## Quickstart

(temporary)

Clone the repo and navigate to it:

```shell
git clone https://github.com/biocommons/anyvar
cd anyvar
```

Point `ANYVAR_STORAGE_URI` to an available PostgreSQL database:

```
export ANYVAR_STORAGE_URI=postgresql://postgres@localhost:5432/anyvar
```

Set `SEQREPO_DATAPROXY_URI` to local SeqRepo files or to a REST service instance:

```
export SEQREPO_DATAPROXY_URI=seqrepo+file:///usr/local/share/seqrepo/latest
# or
export SEQREPO_DATAPROXY_URI=seqrepo+http://localhost:5000/seqrepo
```

Start the AnyVar server:
```shell
uvicorn anyvar.restapi.main:app --reload
```

## Developer installation

    git clone https://github.com/biocommons/anyvar.git
    cd anyvar
    python3 -mvenv venv
    source venv/bin/activate
    pip install -U setuptools pip
    pip install -e '.[dev]'

Or, more simply:

    make devready
    source venv/3.11/bin/activate

Then, start the REST server with:

    uvicorn anyvar.restapi.main:app

In another terminal:

    curl http://localhost:8000/info


### Setting up Postgres

A Postgres-backed *AnyVar* installation may use any Postgres instance, local
or remote.  The following instructions are for using a docker-based
Postgres instance.

First, run the commands in (README-pg.md)[src/anyvar/storage/README-pg.md]. This will create and start a local Postgres docker instance.

Next, run the commands in (postgres_init.sql)[src/anyvar/storage/postgres_init.sql]. This will create the `anyvar` user with the appropriate permissions and create the `anyvar` database.

## Deployment

NOTE: The authoritative and sole source for version tags is the
repository. When a commit is tagged, that tag is automatically used as
the Python `__version__`, the docker image tag, and the version
reported at the `/info` endpoint.


## Testing

Run with `pytest`:

```shell
% pytest
```

or the Makefile target:

```shell
% make test
```

Use the environment variable `ANYVAR_TEST_STORAGE_URI` to specify the database to use for tests, eg:

```shell
% export ANYVAR_TEST_STORAGE_URI=postgresql://postgres:postgres@localhost/anyvar_test_db
```

Currently, there is some interdependency between test modules -- namely, tests that rely on reading data from storage assume that the data from `test_variation` has been uploaded. A pytest hook ensures correct test order, but some test modules may not be able to pass when run in isolation.
