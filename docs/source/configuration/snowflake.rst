Snowflake Data Warehouse Support
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

*AnyVar* can be run using Snowflake as a backend database. Snowflake is a data warehouse rather
than a transactional database such as PostgreSQL. Transactional databases have strong protections
against duplicate keys; data warehouses generally lack these protections due to the performance cost
when handling large volumes of data. AnyVar has configuration options that allow some degree of
control over how these differences are handled.

Setting up Snowflake
---------------------

The Snowflake database and schema must exist prior to starting *AnyVar*. To point
*AnyVar* at Snowflake, specify a Snowflake URI in the ``ANYVAR_STORAGE_URI`` environment
variable. For example::

    snowflake://sf_username:@sf_account_identifier/sf_db_name/sf_schema_name?password=sf_password

See the `Snowflake connection parameter reference <https://docs.snowflake.com/en/developer-guide/python-connector/python-connector-api>`_
for more details.

When running the AnyVar server from an interactive session and connecting to a Snowflake
account that utilizes federated authentication or SSO, add the parameter ``authenticator=externalbrowser``.
When AnyVar starts up, a browser window will open to allow the user to authenticate.
Note that if AnyVar is run with multiple workers, each worker will need to be authenticated
separately.  This is useful for development and testing, but not practical for production deployments.

Non-interactive execution in a federated authentication or SSO environment
requires a service account to connect. Connections using an encrypted or unencrypted
private key are also supported by specifying the parameter ``private_key=path/to/file.p8``.
The key material may be URL-encoded and inlined in the connection URI,
for example::

    private_key=-----BEGIN+PRIVATE+KEY-----%0AMIIEvAIBA...

The pass phrase for the private key file may be specified with the ``ANYVAR_SNOWFLAKE_STORE_PRIVATE_KEY_PASSPHRASE``
environment variable.

Data Management Configuration Options
--------------------------------------

There are two options that can be used to alter data management behavior to better align
with Snowflake's capabilities: the type of table used and whether to attempt to prevent
duplicate rows in the tables.

Dynamic Tables
~~~~~~~~~~~~~~

The ``ANYVAR_SNOWFLAKE_STORE_USE_DYNAMIC_TABLES`` environment variable can be used to instruct
AnyVar to create `dynamic tables <https://docs.snowflake.com/en/user-guide/dynamic-tables-about>`_.
Dynamic tables are materialized views that can be configured to automatically refreshed when
dependent data is changed. Because the ``SequenceReference``, ``Allele`` and ``Location`` entities are
all derivable from the ``VrsObject`` entity, those 3 tables are good candidates for dynamic
tables. Using dynamic tables improves performance by eliminating the need to insert the
same data into multiple tables and leverages the more efficient processes within Snowflake
to keep ``SequenceReference``, ``Allele`` and ``Location`` tables up-to-date.

If dynamic tables are enabled, the ``ANYVAR_SNOWFLAKE_STORE_DYNAMIC_TABLE_OPTS`` environment
variable can be used to specify dynamic table creation options. If options are not specified
the required options are defaulted to ``WAREHOUSE = [current_warehouse] TARGET_LAG = '1 hour'``.

*NOTE*: Currently only ``Allele`` objects in the ``VrsObject`` table are supported when using
dynamic tables. Other VRS object types will be ignored when populating the ``Allele``,
``Location``, and ``SequenceReference`` tables.

Join-Based Merge
~~~~~~~~~~~~~~~~

The ``ANYVAR_SNOWFLAKE_STORE_USE_JOIN_FOR_MERGE`` environment variable can be used to instruct
AnyVar to use an outer join to the target table to avoid inserting duplicate records. Because
Snowflake tables do not enforce primary keys or unique constraints, this is the only method
of preventing duplicates as part of the insert statement. The insert statement is re-written
from:

.. code-block:: sql

    INSERT INTO target_table (id_col, col1) VALUES (?, ?)

To:

.. code-block:: sql

    INSERT INTO target_table (id_col, col1)
    SELECT v.$1, v.$2
      FROM VALUES (?, ?) v
      LEFT OUTER JOIN target_table tt ON tt.id_col = v.$1
     WHERE tt.id_col IS NULL

The performance penalty associated with using a JOIN on the insert will grow as the size
of the target table grows.

Default Configuration
~~~~~~~~~~~~~~~~~~~~~

The default configuration is ``ANYVAR_SNOWFLAKE_STORE_USE_DYNAMIC_TABLES=false`` and
``ANYVAR_SNOWFLAKE_STORE_USE_JOIN_FOR_MERGE=true``, which mimics the data management behavior
of a transactional database, but with the aforementioned performance penalty.
