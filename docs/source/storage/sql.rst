SQL Database Setup
!!!!!!!!!!!!!!!!!!

A Postgres database may optionally be used with AnyVar. This database is used to cache variants that have been transformed by AnyVar. Use the ``ANYVAR_STORAGE_URI`` environment variable to define the database connection URL (see the documentation for your chosen database implementation for more details). AnyVar uses `SQLAlchemy 1.4 <https://docs.sqlalchemy.org/en/14/index.html>`_ to provide database connection management. The default database connection URL is ``postgresql://postgres@localhost:5432/anyvar``.

The Postgres database connector utilizes a background thread to write VRS objects to the database when operating in batch mode (e.g. annotating a VCF file). Queries and statistics query only against the already committed database state. Therefore, queries issued immediately after a batch operation may not reflect all pending changes if the ``ANYVAR_SQL_STORE_FLUSH_ON_BATCHCTX_EXIT`` parameter is set to ``False``.

Cheat Sheet: Environment Variables
----------------------------------

The database integrations can be modified using the following parameters in your ``.env`` file:

.. list-table::
   :widths: 20 40 40
   :header-rows: 1

   * - Variable
     - Description
     - Default
   * - ``ANYVAR_STORAGE_URI``
     - The URI for your chosen storage method. Set to an empty string (`""`) if running AnyVar without a storage option configured
     - (no default)
   * - ``ANYVAR_SQL_STORE_BATCH_LIMIT``
     - In batch mode, limit VRS object upsert batches to this number
     - ``100000``
   * - ``ANYVAR_SQL_STORE_TABLE_NAME``
     - The name of the table that stores VRS objects
     - ``vrs_objects``
   * - ``ANYVAR_SQL_STORE_MAX_PENDING_BATCHES``
     - The maximum number of pending batches to allow before blocking
     - ``50``
   * - ``ANYVAR_SQL_STORE_FLUSH_ON_BATCHCTX_EXIT``
     - Whether or not flush all pending database writes when the batch manager exists
     - ``True``
