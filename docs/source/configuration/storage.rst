Object Storage Configuration
!!!!!!!!!!!!!!!!!!!!!!!!!!!!

Storage Connection
==================

Use the ``ANYVAR_STORAGE_URI`` environment variable to pass a `libpq connection string <https://www.postgresql.org/docs/current/libpq.html>`_ to the PostgreSQL connection constructor, or an empty string (``""``) to use :ref:`stateless mode <stateless_mode>`.

.. list-table::
   :widths: 30 70
   :header-rows: 1

   * - Environment Variable
     - Default Value
   * - ``ANYVAR_STORAGE_URI``
     - ``"postgresql://postgres@localhost:5432/anyvar"``


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
   * - ``ANYVAR_ANNOTATIONS_TABLE_NAME``
     - ``"annotations"``
   * - ``ANYVAR_LOCATIONS_TABLE_NAME``
     - ``"locations"``
   * - ``ANYVAR_SEQUENCE_REFERENCES_TABLE_NAME``
     - ``"sequence_references"``
   * - ``ANYVAR_VARIATION_MAPPINGS_TABLE_NAME``
     - ``"variation_mappings"``
   * - ``ANYVAR_VRS_OBJECTS_TABLE_NAME``
     - ``"vrs_objects"``
