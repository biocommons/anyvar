Configuration
!!!!!!!!!!!!!

This section details AnyVar configuration. It is broken down into the following subsections:

* :doc:`Object Storage <storage>`: define database connection, alter table names, and set parameters for bulk processing
* :doc:`Snowflake Storage <snowflake>`: configure AnyVar to use Snowflake as the object storage backend
* :doc:`Asynchronous Processing <async>`: set parameters for Celery-based queued task processing
* :doc:`Authentication <authentication>`: configure bearer token authentication for REST API endpoints
* :doc:`Logging <logging>`: configure application logging
* :doc:`Service-Info <service_info>`: declare values related to application identity for the :ref:`service-info API endpoint <get_service_info>`
* :doc:`Example .env file <dotenv_example>`: use a ``.env`` file to declare environment variables when running REST API service
* :doc:`Docker Compose <docker_compose>`: edit the provided Docker Compose file to tailor it to your needs

.. toctree::
   :maxdepth: 2
   :hidden:

   Storage<storage>
   Snowflake Storage<snowflake>
   Asynchronous Processing<async>
   Authentication<authentication>
   Logging<logging>
   Service-Info<service_info>
   Example .env file<dotenv_example>
   Docker Compose<docker_compose>
