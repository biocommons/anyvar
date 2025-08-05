.. _postgresql-setup:

AnyVar PostgreSQL Setup
!!!!!!!!!!!!!!!!!!!!!!!

AnyVar supports PostgreSQL for persistent storage of variation data and associated metadata. PostgreSQL setup is recommended for production environments or heavy-use scenarios.

PostgreSQL Overview
===================

Using PostgreSQL allows AnyVar to efficiently store, retrieve, and manage variation data, ensuring reliability and performance for your applications.

Docker-based PostgreSQL Setup (Recommended)
===========================================

Docker is the simplest and most efficient method to set up PostgreSQL quickly.

1. Pull PostgreSQL Docker Image
-------------------------------

::

    docker pull postgres

2. Start PostgreSQL Docker Container
------------------------------------

Create and run a PostgreSQL container

.. code-block:: shell

    docker run -d \
      --name anyvar-pg \
      -p 5432:5432 \
      -e POSTGRES_PASSWORD=postgres \
      postgres

    cat src/anyvar/storage/postgres_init.sql | psql -h localhost -U postgres -p 5432

3. Configure the environment variable to connect AnyVar to PostgreSQL
---------------------------------------------------------------------

Set the following environment variable in your ``.env`` file:

.. code-block:: shell

    ANYVAR_STORAGE_URI=postgresql://anyvar:anyvar-pw@localhost:5432/anyvar

Verifying Container Setup
--------------------------

Confirm your PostgreSQL container is running:

.. code-block:: shell

    % docker ps | grep anyvar-pg
    64c607968fa5   postgres          "docker-entrypoint.s…"   6 seconds ago   Up 6 seconds   0.0.0.0:5432->5432/tcp     anyvar-pg


You should see the container listed and running.

Initializing Database Schema and User Permissions
-------------------------------------------------

AnyVar expects specific database credentials (``anyvar`` user and ``anyvar`` database by default).

Troubleshooting and Validation
------------------------------

* **Port Conflicts:** If the default port (``5432``) is unavailable, try running the following command:

.. code-block:: shell

    docker run -d \
    --name anyvar-postgres \
    -e POSTGRES_USER=anyvar \
    -e POSTGRES_PASSWORD=anyvar-pw \
    -e POSTGRES_DB=anyvar \
    -p 5433:5432 \
    postgres:latest

    export ANYVAR_STORAGE_URI=postgresql://anyvar:anyvar-pw@localhost:5433/anyvar

* **Inspect Container Logs:** Check logs if issues arise:

.. code-block:: shell

  docker logs anyvar-postgres

* **Database Connectivity Test:** Test PostgreSQL connection with psql:

.. code-block:: shell

    psql -h localhost -U anyvar -d anyvar

A successful connection confirms correct setup.

Cheat Sheet: Environment Variables
----------------------------------

.. list-table::
   :widths: 20 40 40
   :header-rows: 1

   * - Variable
     - Description
     - Example
   * - ``ANYVAR_STORAGE_URI``
     - PostgreSQL connection URL
     - ``postgresql://anyvar:anyvar-pw@localhost:5432/anyvar``
