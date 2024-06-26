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
export ANYVAR_STORAGE_URI=postgresql://anyvar:anyvar-pw@localhost:5432/anyvar
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


### SQL Database Setup
A Postgres or Snowflake database may be used with *AnyVar*.  The Postgres database
may be either local or remote.  Use the  `ANYVAR_STORAGE_URI` environment variable
to define the database connection URL.  *AnyVar* uses [SQLAlchemy 1.4](https://docs.sqlalchemy.org/en/14/index.html) 
to provide database connection management.  The default database connection URL
is `"postgresql://postgres@localhost:5432/anyvar"`.

The database integrations can be modified using the following parameters:
* `ANYVAR_SQL_STORE_BATCH_LIMIT` - in batch mode, limit VRS object upsert batches 
to this number; defaults to `100,000`
* `ANYVAR_SQL_STORE_TABLE_NAME` - the name of the table that stores VRS objects; 
defaults to `vrs_objects`
* `ANYVAR_SQL_STORE_MAX_PENDING_BATCHES` - the maximum number of pending batches 
to allow before blocking; defaults to `50`
* `ANYVAR_SQL_STORE_FLUSH_ON_BATCHCTX_EXIT` - whether or not flush all pending 
database writes when the batch manager exists; defaults to `True`

The Postgres and Snowflake database connectors utilize a background thread 
to write VRS objects to the database when operating in batch mode (e.g. annotating 
a VCF file).  Queries and statistics query only against the already committed database 
state.  Therefore, queries issued immediately after a batch operation may not reflect 
all pending changes if the `ANYVAR_SQL_STORE_FLUSH_ON_BATCHCTX_EXIT` parameter is sett
to `False`.

#### Setting up Postgres
The following instructions are for using a docker-based Postgres instance.

First, run the commands in [README-pg.md](src/anyvar/storage/README-pg.md). 
This will create and start a local Postgres docker instance.

Next, run the commands in [postgres_init.sql](src/anyvar/storage/postgres_init.sql). 
This will create the `anyvar` user with the appropriate permissions and create the 
`anyvar` database.

#### Setting up Snowflake
The Snowflake database and schema must exist prior to starting *AnyVar*.  To point
*AnyVar* at Snowflake, specify a Snowflake URI in the `ANYVAR_STORAGE_URI` environment
variable.  For example:
```
snowflake://sf_username:@sf_account_identifier/sf_db_name/sf_schema_name?password=sf_password
```
[Snowflake connection parameter reference](https://docs.snowflake.com/en/developer-guide/python-connector/python-connector-api)

When running interactively and connecting to a Snowflake account that utilizes 
federated authentication or SSO, add the parameter `authenticator=externalbrowser`.  
Non-interactive execution in a federated authentication or SSO environment
requires a service account to connect.  Connections using an encrypted or unencrypted 
private key are also supported by specifying the parameter `private_key=path/to/file.p8`.
The key material may be URL-encoded and inlined in the connection URI, 
for example: `private_key=-----BEGIN+PRIVATE+KEY-----%0AMIIEvAIBA...`

Environment variables that can be used to modify Snowflake database integration:
* `ANYVAR_SNOWFLAKE_STORE_PRIVATE_KEY_PASSPHRASE` - the passphrase for an encrypted private key
* `ANYVAR_SNOWFLAKE_BATCH_ADD_MODE` - the SQL statement type to use when adding new VRS objects, one of:
    * `merge` (default) - use a MERGE statement.  This guarantees that duplicate VRS IDs will
    not be added, but also locks the VRS object table, limiting throughput.
    * `insert_notin` - use INSERT INTO vrs_objects SELECT FROM tmp WHERE vrs_id NOT IN (...).
    This narrows the chance of duplicates and does not require a table lock.
    * `insert` - use INSERT INTO.  This maximizes throughput at the cost of not checking for
    duplicates at all.

If you choose to create the VRS objects table in advance, the minimal table specification is as follows:
```sql
CREATE TABLE ... (
    vrs_id VARCHAR(500) COLLATE 'utf8',
    vrs_object VARIANT
)
```

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
% export ANYVAR_TEST_STORAGE_URI=postgresql://postgres:postgres@localhost/anyvar_test
```

Currently, there is some interdependency between test modules -- namely, tests that rely on reading data from storage assume that the data from `test_variation` has been uploaded. A pytest hook ensures correct test order, but some test modules may not be able to pass when run in isolation.  By default, the tests will use a Postgres database
installation.  To run the tests against a Snowflake database, change the `ANYVAR_TEST_STORAGE_URI` to a Snowflake URI and run the tests.
