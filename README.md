# AnyVar

*AnyVar* provides Python and REST interfaces to validate, normalize, generate
identifiers, and register biological sequence variation according to the
[GA4GH Variation Representation Specification (VRS)](https://github.com/ga4gh/vrs).

## Information

[![license](https://img.shields.io/badge/license-Apache-green)](https://github.com/biocommons/anyvar/blob/main/LICENSE)

## Development

[![issues](https://img.shields.io/github/issues-raw/biocommons/anyvar.svg)](https://github.com/biocommons/anyvar/issues)
[![GitHub Open Pull Requests](https://img.shields.io/github/issues-pr/biocommons/anyvar.svg)](https://github.com/biocommons/anyvar/pull/) [![GitHub Contributors](https://img.shields.io/github/contributors/biocommons/anyvar.svg)](https://github.com/biocommons/anyvar/graphs/contributors/) [![GitHub stars](https://img.shields.io/github/stars/biocommons/anyvar.svg?style=social&label=Stars)](https://github.com/biocommons/anyvar/stargazers) [![GitHub forks](https://img.shields.io/github/forks/biocommons/anyvar.svg?style=social&label=Forks)](https://github.com/biocommons/anyvar/network)

## Known Issues

**You are encouraged to** [browse issues](https://github.com/biocommons/anyvar/issues).
All known issues are listed there. Please report any issues you find.

## Quick Start

Clone the repo and navigate to it:

```shell
git clone https://github.com/biocommons/anyvar
cd anyvar
```

Point `ANYVAR_STORAGE_URI` to an available PostgreSQL database:

```shell
export ANYVAR_STORAGE_URI=postgresql://anyvar:anyvar-pw@localhost:5432/anyvar
```

Set `SEQREPO_DATAPROXY_URI` to local SeqRepo files:

```shell
export SEQREPO_DATAPROXY_URI=seqrepo+file:///usr/local/share/seqrepo/latest
```

Or set `SEQREPO_DATAPROXY_URI` to a REST service instance:

```shell
export SEQREPO_DATAPROXY_URI=seqrepo+http://localhost:5000/seqrepo
```

Start the AnyVar server:

```shell
uvicorn anyvar.restapi.main:app --reload
```

## Developers

This section is intended for developers who contribute to AnyVar.

### Prerequisites

- Python >= 3.9
  - _Note: Python 3.11 is required for developers contributing to AnyVar
- [Docker](https://docs.docker.com/engine/install/)

### Installing for development

```shell
git clone https://github.com/biocommons/anyvar.git
cd anyvar
make devready
source venv/3.11/bin/activate
pre-commit install
```

### SeqRepo

First, you must install a local [SeqRepo](https://github.com/biocommons/biocommons.seqrepo):

```shell
pip install seqrepo
export SEQREPO_VERSION=2024-02-20
sudo mkdir -p /usr/local/share/seqrepo
sudo chown $USER /usr/local/share/seqrepo
seqrepo pull -i $SEQREPO_VERSION
seqrepo update-latest
```

> NOTE: To check for the presence of newer snapshots, use the seqrepo list-remote-instances CLI command.

If you encounter a permission error similar to the one below:

```shell
PermissionError: [Error 13] Permission denied: '/usr/local/share/seqrepo/2024-02-20._fkuefgd' -> '/usr/local/share/seqrepo/2024-02-20'
```

Try moving data manually with `sudo`:

```shell
sudo mv /usr/local/share/seqrepo/$SEQREPO_VERSION.* /usr/local/share/seqrepo/$SEQREPO_VERSION
```

#### SeqRepo REST

We recommend using Docker to install
[SeqRepo REST](https://github.com/biocommons/seqrepo-rest-service).

### SQL Database Setup

A Postgres or Snowflake database may be used with *AnyVar*. The Postgres database
may be either local or remote. Use the  `ANYVAR_STORAGE_URI` environment variable
to define the database connection URL. *AnyVar* uses
[SQLAlchemy 1.4](https://docs.sqlalchemy.org/en/14/index.html) to provide database
connection management. The default database connection URL
is `postgresql://postgres@localhost:5432/anyvar`.

The database integrations can be modified using the following parameters:

- `ANYVAR_SQL_STORE_BATCH_LIMIT` - in batch mode, limit VRS object upsert batches to
  this number; defaults to `100,000`
- `ANYVAR_SQL_STORE_TABLE_NAME` - the name of the table that stores VRS objects;
  defaults to `vrs_objects`
- `ANYVAR_SQL_STORE_MAX_PENDING_BATCHES` - the maximum number of pending batches to
  allow before blocking; defaults to `50`
- `ANYVAR_SQL_STORE_FLUSH_ON_BATCHCTX_EXIT` - whether or not flush all pending database
  writes when the batch manager exists; defaults to `True`

The Postgres and Snowflake database connectors utilize a background thread
to write VRS objects to the database when operating in batch mode (e.g. annotating
a VCF file). Queries and statistics query only against the already committed database
state. Therefore, queries issued immediately after a batch operation may not reflect
all pending changes if the `ANYVAR_SQL_STORE_FLUSH_ON_BATCHCTX_EXIT` parameter is sett
to `False`.

#### Setting up Postgres

The following instructions are for using a docker-based Postgres instance.

First, run the commands in [README-pg.md](src/anyvar/storage/README-pg.md).
This will create and start a local Postgres docker instance. It will also create the
`anyvar` user with the appropriate permissions and create the `anyvar` database.

#### Setting up Snowflake

The Snowflake database and schema must exist prior to starting *AnyVar*. To point
*AnyVar* at Snowflake, specify a Snowflake URI in the `ANYVAR_STORAGE_URI` environment
variable. For example:

```markdown
snowflake://sf_username:@sf_account_identifier/sf_db_name/sf_schema_name?password=sf_password
```

[Snowflake connection parameter reference](https://docs.snowflake.com/en/developer-guide/python-connector/python-connector-api)

When running interactively and connecting to a Snowflake account that utilizes
federated authentication or SSO, add the parameter `authenticator=externalbrowser`.
Non-interactive execution in a federated authentication or SSO environment
requires a service account to connect. Connections using an encrypted or unencrypted
private key are also supported by specifying the parameter `private_key=path/to/file.p8`.
The key material may be URL-encoded and inlined in the connection URI,
for example: `private_key=-----BEGIN+PRIVATE+KEY-----%0AMIIEvAIBA...`

Environment variables that can be used to modify Snowflake database integration:

- `ANYVAR_SNOWFLAKE_STORE_PRIVATE_KEY_PASSPHRASE` - the passphrase for an encrypted private key
- `ANYVAR_SNOWFLAKE_BATCH_ADD_MODE` - the SQL statement type to use when adding new VRS objects, one of:
  - `merge` (default) - use a MERGE statement. This guarantees that duplicate VRS IDs will
    not be added, but also locks the VRS object table, limiting throughput.
  - `insert_notin` - use INSERT INTO vrs_objects SELECT FROM tmp WHERE vrs_id NOT IN (...).
    This narrows the chance of duplicates and does not require a table lock.
  - `insert` - use INSERT INTO. This maximizes throughput at the cost of not checking for
    duplicates at all.

If you choose to create the VRS objects table in advance, the minimal table specification is as follows:

```sql
CREATE TABLE ... (
    vrs_id VARCHAR(500) COLLATE 'utf8',
    vrs_object VARIANT
)
```

### Enabling Asynchronous VCF Annotation
AnyVar can support using the asynchronous request-response pattern when annotating VCF files.
This can improve reliability when serving remote clients by eliminating long lived connections
and allow AnyVar to scale out instead of up to serve a larger request volume.

See [README-async.md](README-async.md) for more details.

### Starting the REST service locally

Once the data dependencies are setup, start the REST server with:

```shell
uvicorn anyvar.restapi.main:app
```

In another terminal:

```shell
curl http://localhost:8000/info
```

## Testing

To run tests:

```shell
make test
```

Use the environment variable `ANYVAR_TEST_STORAGE_URI` to specify the database to use
for tests, eg:

```shell
% export ANYVAR_TEST_STORAGE_URI=postgresql://postgres:postgres@localhost/anyvar_test
```

Currently, there is some interdependency between test modules -- namely, tests that rely
on reading data from storage assume that the data from `test_variation` has been
uploaded. A pytest hook ensures correct test order, but some test modules may not be
able to pass when run in isolation. By default, the tests will use a Postgres database
installation. To run the tests against a Snowflake database, change the
`ANYVAR_TEST_STORAGE_URI` to a Snowflake URI and run the tests.

For the `tests/test_vcf::test_vcf_registration_async` unit test to pass, a real broker and backend
are required for Celery to interact with.  Set the `CELERY_BROKER_URL` and `CELERY_BACKEND_URL`
environment variables.  The simplest solution is to run Redis locally and use that for both
the broker and the backend, eg:
```shell
% export CELERY_BROKER_URL="redis://"
% export CELERY_BACKEND_URL="redis://"
```

## Logging
AnyVar uses the [Python Logging Module](https://docs.python.org/3/howto/logging.html) to
output information and diagnostics.  By default, log output is directed to standard output
and the level is set to `INFO`.  Alternatively, a YAML logging configuration may be specified
using the `ANYVAR_LOGGING_CONFIG` environment variable.  The value must be the relative or
absolute path of a YAML file containing a valid logging configuration. The configuration
in this file will be loaded and used to configured the logging module.

For example:
```yaml
version: 1
disable_existing_loggers: true

formatters:
  standard:
    format: "%(threadName)s %(asctime)s - %(name)s - %(levelname)s - %(message)s"

handlers:
  console:
    class: logging.StreamHandler
    level: DEBUG
    formatter: standard
    stream: ext://sys.stdout

root:
  level: INFO
  handlers: [console]
  propagate: yes

loggers:
  anyvar.restapi.main:
    level: INFO
    handlers: [console]
    propagate: no

  anyvar.storage.sql_storage:
    level: DEBUG
    handlers: [console]
    propagate: no
```
