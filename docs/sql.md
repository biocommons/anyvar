# SQL Database Setup

A Postgres or Snowflake database may optionally be used with *AnyVar*. Use the  `ANYVAR_STORAGE_URI` environment variable
to define the database connection URL (see the documentation for your chosen database implementation for more details). *AnyVar* uses
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
