Configuration
!!!!!!!!!!!!!

This section details AnyVar configuration. It is broken down into the following subsections:

* :doc:`Object Storage <storage>`: define database connection, alter table names, and set parameters for bulk processing
* :doc:`Asynchronous Processing <async>`: set parameters for Celery-based queued task processing
* :doc:`Logging <logging>`: configure application logging
* :doc:`Service-Info <service_info>`: declare values related to application identity for the :ref:`service-info API endpoint <get_service_info>`
* :doc:`Example .env file <dotenv_example>`: use a ``.env`` file to declare environment variables when running REST API service

.. toctree::
   :maxdepth: 2
   :hidden:

   Storage<storage>
   Asynchronous Processing<async>
   Logging<logging>
   Service-Info<service_info>
   Example .env file<dotenv_example>
