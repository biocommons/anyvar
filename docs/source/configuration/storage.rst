Object Storage
!!!!!!!!!!!!!!

.. TODO decide on this last

   Cheat Sheet
   ===========

   insert table here

   ANYVAR_STORAGE_URI
   ANYVAR_SQL_STORE_BATCH_LIMIT=10000
   ANYVAR_SQL_STORE_TABLE_NAME=vrs_objects
   ANYVAR_SQL_STORE_MAX_PENDING_BATCHES=50
   ANYVAR_SQL_STORE_FLUSH_ON_BATCHCTX_EXIT=True
   <table rename>

Storage Connection
==================

Use the ``ANYVAR_STORAGE_URI`` environment variable to pass a `libpq connection string <https://www.postgresql.org/docs/current/libpq.html>`_ to the PostgreSQL connection constructor, or an empty string (`""`) to use :ref:`stateless mode <stateless_mode>`.

example, default value

Rename Tables
=============

.. TODO

Other Storage Configurations
============================

.. TODO

ANYVAR_SQL_STORE_BATCH_LIMIT=10000
ANYVAR_SQL_STORE_TABLE_NAME=vrs_objects
ANYVAR_SQL_STORE_MAX_PENDING_BATCHES=50
ANYVAR_SQL_STORE_FLUSH_ON_BATCHCTX_EXIT=True
