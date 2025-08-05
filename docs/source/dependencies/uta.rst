.. _uta-setup:

AnyVar UTA Setup
!!!!!!!!!!!!!!!!

`UTA (Universal Transcript Archive) <https://github.com/biocommons/uta>`_ is used to interpret variations on non-genomic sequences, such as transcript-based accessions. It is required for AnyVar operations involving transcript coordinates.

Recommended Public Instance Usage (for small use cases)
=======================================================

For **minimal** usage scenarios, utilize the public UTA instance hosted by `biocommons.org <https://biocommons.org>`_ by setting the following variable in your ``.env`` file:

.. code-block:: shell

    UTA_DB_URL="postgresql://anonymous:anonymous@uta.biocommons.org:5432/uta/uta_20210129b"

This public instance is convenient but may experience slower performance during peak usage.

Docker Installation (Recommended for larger workloads)
======================================================

A local Docker setup is recommended for consistent performance and reliability.

Prerequisites
-------------

* Ensure Docker and Docker Compose are installed.

  * `Docker Installation <https://docs.docker.com/get-docker/>`_
  * `Docker Compose Installation <https://docs.docker.com/compose/install/>`_

1. Fetch UTA Docker Image
-------------------------

.. code-block:: shell

    uta_version=uta_20241220
    docker pull biocommons/uta:${uta_version}

This process will likely take 1-3 minutes.

2. Create and Populate Docker Volume
------------------------------------

Create a persistent volume to store UTA data:

.. code-block:: shell

    docker volume create uta_vol

3. Run the UTA Docker Container
-------------------------------

Start the container and populate the database:

.. code-block::

    docker run  --platform linux/amd64 -d --rm -e POSTGRES_PASSWORD=uta \
      -v uta_vol:/var/lib/postgresql/dat  a \
      --name $uta_version -p 5432:5432 biocommons/uta:${uta_version}

4. Monitor data population (initial run only)
---------------------------------------------

::

    docker logs -f $uta_version

Once the log indicates readiness (``database system is ready``), your UTA installation is active.

5. Set Environment Variable
---------------------------

Configure AnyVar to use UTA by setting the following variable in your ``.env`` file: ::

    UTA_DB_URL="postgresql://anonymous@localhost:5432/uta/uta_20241220"

Verifying UTA Installation
--------------------------

Check database connectivity using PostgreSQL CLI:

.. code-block:: python

    psql -h localhost -U anonymous -d uta -c "select * from uta_20241220.meta"

A successful query returns metadata indicating the version and setup details.

Troubleshooting and Validation
------------------------------

* **Connection Issues:** Ensure port ``5432`` is available, or change the port if conflicts arise. Be sure to update your ``UTA_DB_URL`` environment variable if you change the port number.

.. code-block:: shell

  docker run --platform linux/amd64 -d --rm -e POSTGRES_PASSWORD=uta \
  -v uta_vol:/var/lib/postgresql/data \
  --name $uta_version -p 5433:5432 biocommons/uta:${uta_version}

  export UTA_DB_URL=postgresql://anonymous@localhost:5433/uta/uta_20241220

* **Volume Persistence:** Verify volume status:

.. code-block:: shell

  docker volume inspect uta_vol

* **Docker Container Logs:** Check logs for container issues:

.. code-block:: shell

  docker logs $uta_version

Cheat Sheet: Environment Variables
==================================

.. list-table::
   :widths: 20 40 40
   :header-rows: 1

   * - Variable
     - Description
     - Example
   * - ``UTA_DB_URL``
     - Database connection URL for UTA
     - ``postgresql://anonymous@localhost:5432/uta/uta_20241220``
