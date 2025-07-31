.. _seqrepo-setup:

AnyVar SeqRepo Setup
!!!!!!!!!!!!!!!!!!!!

SeqRepo is a repository system designed to store and manage biological sequence data efficiently.

Recommended: Local Installation
===============================

The simplest and most efficient method for most users is a direct local file installation.


1. Download the SeqRepo Archive
-------------------------------

::

    curl -O https://storage.googleapis.com/clingen-public/seqrepo_2024-12-20.tar.gz

2. Create a SeqRepo Directory
-----------------------------

Create a SeqRepo directory, then extract the download inside of it

::

    mkdir seqrepo
    tar -xzvf seqrepo_2024-12-20.tar.gz -C seqrepo

3. Set the Environment Variable
-------------------------------

Configure your environment to point to this SeqRepo location by setting the following variable in your `.env` file: ::

    SEQREPO_DATAPROXY_URI="seqrepo+file:///full/path/to/seqrepo/2024-12-20"

Replace ``/full/path/to/seqrepo`` with your absolute path.

Docker-based Installation
=========================

Docker is suitable for containerized environments or users preferring isolation.

Prerequisites
-------------

* Ensure Docker and Docker Compose are installed.

  * `Docker Installation <https://docs.docker.com/get-docker/>`_
  * `Docker Compose Installation <https://docs.docker.com/compose/install/>`_

1. Create a Docker Volume
-------------------------

::

    docker volume create seqrepo-vol

2. Populate the Volume With a SeqRepo Snapshot
----------------------------------------------

::

	docker run -it --rm -v seqrepo-vol:/usr/local/share/seqrepo docker.io/biocommons/seqrepo:2024-12-20

.. NOTE::

    This downloads and syncs the SeqRepo database into the volume. It may take a while.

3. Pull the SeqRepo REST Service Image
--------------------------------------

::

    docker pull biocommons/seqrepo-rest-service

4. Start SeqRepo REST Service
-----------------------------

Run the REST service to provide access through HTTP. Choose an appropriate local port - the example below uses ``5001``, but you can pick anything you'd like. ::

    docker run -d --name seqrepo-rest \
    -v seqrepo-vol:/usr/local/share/seqrepo \
    -p 5001:5000 biocommons/seqrepo-rest-service \
    seqrepo-rest-service /usr/local/share/seqrepo/2024-12-20

5. Set your environment variable to the REST API
------------------------------------------------

Set the following environment variables in your ``.env`` file: ::

    SEQREPO_DATAPROXY_URI="seqrepo+http://localhost:5001/seqrepo"
    SEQREPO_INSTANCE_DIR="/usr/local/share/seqrepo/2024-12-20"

Native Installation (rsync-based)
==================================

Useful when direct file or Docker setups are not feasible.

1. Install SeqRepo
------------------

::

    pip install seqrepo

2. Prepare directories
----------------------

::

    export SEQREPO_VERSION=2024-12-20
    sudo mkdir -p /usr/local/share/seqrepo
    sudo chown $USER /usr/local/share/seqrepo

3. Fetch data with ``rsync``
----------------------------

::

    seqrepo pull -i $SEQREPO_VERSION
    seqrepo update-latest

4. Configure environment
------------------------

Set the environment variable in your ``.env`` file accordingly:

::

    SEQREPO_DATAPROXY_URI=seqrepo+file:///usr/local/share/seqrepo/$SEQREPO_VERSION

Troubleshooting
---------------

* If your institution blocks rsync, consider using the direct download method or Docker.
* Ensure you have the correct `rsync` executable: GNU rsync, NOT openrsync.
* Check your rsync version: ::

    rsync --version

* If you encounter a permission error like this: ::

    PermissionError: [Error 13] Permission denied: '/usr/local/share/seqrepo/2024-02-20._fkuefgd' -> '/usr/local/share/seqrepo/2024-02-20'


Try moving data manually with ``sudo``: ::

    sudo mv /usr/local/share/seqrepo/$SEQREPO_VERSION.* /usr/local/share/seqrepo/$SEQREPO_VERSION

Verifying SeqRepo Installation
==============================

Verify local setup with Python:


.. code-block:: python

    from ga4gh.vrs.dataproxy import create_dataproxy
    uri = "seqrepo+file:///full_path_to_seqrepo/2024-12-20"
    seqrepo_dataproxy = create_dataproxy(uri=uri)
    sequence = seqrepo_dataproxy.get_sequence("refseq:NM_000551.3")
    print(sequence[:100])


For REST API verification:

.. code-block:: shell

    curl http://localhost:5001/seqrepo/1/sequence/refseq:NM_000551.3

Successful completion of these steps confirms a working SeqRepo installation.

Cheat Sheet: Environment Variables
==================================

.. list-table::
   :widths: 20 40 40
   :header-rows: 1

   * - Variable
     - Description
     - Example
   * - ``SEQREPO_DATAPROXY_URI``
     - URI for SeqRepo DataProxy interface.
     - ``seqrepo+file:///usr/local/share/seqrepo/2024-12-20``
   * - ``SEQREPO_INSTANCE_DIR``
     - Path to the SeqRepo install (only required Docker-based installation)
     - ``"/usr/local/share/seqrepo/2024-12-20"``
