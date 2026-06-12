Object Storage Configuration
!!!!!!!!!!!!!!!!!!!!!!!!!!!!

Storage Connection
==================

AnyVar supports several different database engines. Use the ``ANYVAR_STORAGE_URI`` environment variable to designate the database engine and its location.

.. list-table::
   :widths: 30 70
   :header-rows: 1

   * - Environment Variable
     - Default Value
   * - ``ANYVAR_STORAGE_URI``
     - ``"postgresql://postgres@localhost:5432/anyvar"``


* A `libpq connection string <https://www.postgresql.org/docs/current/libpq.html>`_ constructs a PostgreSQL connection. This is the default database engine and is recommended for most use cases.
* A URI with a ``snowflake://`` scheme constructs a Snowflake connection. See the :ref:`AnyVar Snowflake configuration <snowflake>` page for more information.
* a URI with a ``duckdb://`` scheme constructs a `DuckDB <https://duckdb.org/>`_ connection. Use a relative file path, eg ``duckdb:///my_variants.duckdb``, for a file-based instance, or ``duckdb:///:memory:`` for an in-memory instance. See the :py:class:`~anyvar.storage.duckdb` API reference page for more information.
* An empty string (ie ``export ANYVAR_STORAGE_URI=""``) enables :ref:`stateless mode <stateless_mode>`.



Rename Tables
=============

For cases where AnyVar storage is shared with other applications and an additional naming scheme may be beneficial, all AnyVar database tables can be renamed by an environment variable of the pattern ``"ANYVAR_<table>_TABLE_NAME"``.

.. list-table::
   :widths: 30 70
   :header-rows: 1

   * - Environment Variable
     - Default Value
   * - ``ANYVAR_ALLELES_TABLE_NAME``
     - ``"alleles"``
   * - ``ANYVAR_EXTENSIONS_TABLE_NAME``
     - ``"extensions"``
   * - ``ANYVAR_LOCATIONS_TABLE_NAME``
     - ``"locations"``
   * - ``ANYVAR_SEQUENCE_REFERENCES_TABLE_NAME``
     - ``"sequence_references"``
   * - ``ANYVAR_VARIATION_MAPPINGS_TABLE_NAME``
     - ``"variation_mappings"``
   * - ``ANYVAR_VRS_OBJECTS_TABLE_NAME``
     - ``"vrs_objects"``
