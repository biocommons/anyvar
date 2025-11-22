Configuring Docker Compose
!!!!!!!!!!!!!!!!!!!!!!!!!!

This page describes how to use the provided ``compose.yaml`` file to start AnyVar alongside its dependencies, and highlights some configuration options you can customize for your environment.

Overview
--------

The compose file defines four main services:

* ``seqrepo`` – provides a SeqRepo instance on a Docker volume
* ``uta`` – UTA database in a PostgreSQL container
* ``anyvar_db`` – PostgreSQL database for AnyVar
* ``anyvar`` – the AnyVar web API, configured to use SeqRepo, UTA, and the AnyVar DB

It also defines three Docker volumes:

* ``seqrepo_vol`` – storage for SeqRepo data
* ``uta_vol`` – storage for the UTA PostgreSQL data directory
* ``anyvar_vol`` – storage for the AnyVar PostgreSQL data directory

All three volumes are declared as ``external: true``, so they must exist before
you run ``docker compose up``. For example:

.. code-block:: bash

   docker volume create seqrepo_vol
   docker volume create uta_vol
   docker volume create anyvar_vol

SeqRepo Options
---------------

The compose file supports several patterns for providing a SeqRepo database to
AnyVar, depending on whether you want Docker to manage the data or reuse an
existing SeqRepo on your local filesystem.

Using the bundled SeqRepo container (default)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

By default, the compose file runs a ``seqrepo`` container that mounts the
``seqrepo_vol`` volume at ``/usr/local/share/seqrepo``:

.. code-block:: yaml

   seqrepo:
     image: biocommons/seqrepo:2024-12-20
     volumes:
       - seqrepo_vol:/usr/local/share/seqrepo

The ``anyvar`` service then mounts the same volume and points its configuration
at the 2024-12-20 snapshot:

.. code-block:: yaml

   anyvar:
     volumes:
       - seqrepo_vol:/usr/local/share/seqrepo
     environment:
       - SEQREPO_INSTANCE_DIR=/usr/local/share/seqrepo/2024-12-20
       - SEQREPO_DATAPROXY_URI=seqrepo+file:///usr/local/share/seqrepo/2024-12-20

This is the simplest option if you are happy to let Docker manage the SeqRepo
storage in an external volume.

Using a host SeqRepo directory directly
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If you already have a SeqRepo database on your local filesystem and want AnyVar
to use it directly (without a dedicated ``seqrepo`` container), you can bind
mount your existing directory into the ``anyvar`` container.

1. Comment out the ``seqrepo`` service in the compose file.
2. Replace the volume mapping under ``anyvar``:

   .. code-block:: yaml

      anyvar:
        volumes:
          - $SEQREPO_ROOT_DIR:/usr/local/share/seqrepo

3. Export ``SEQREPO_ROOT_DIR`` before running compose, pointing it at the root of your local SeqRepo installation:

   .. code-block:: bash

      export SEQREPO_ROOT_DIR=/path/to/my/seqrepo
      docker compose up

4. Keep the environment variables as they are, or adjust if your SeqRepo snapshot directory name differs:

   .. code-block:: yaml

      environment:
        - SEQREPO_INSTANCE_DIR=/usr/local/share/seqrepo/2024-12-20
        - SEQREPO_DATAPROXY_URI=seqrepo+file:///usr/local/share/seqrepo/2024-12-20

Make sure the snapshot path (e.g. ``2024-12-20``) exists under ``$SEQREPO_ROOT_DIR`` and matches ``SEQREPO_INSTANCE_DIR``.

Copying a host SeqRepo into a Docker volume
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If you have a local SeqRepo and prefer to copy it into a Docker-managed
volume (``seqrepo_vol``) rather than bind mounting your host directory each
time, you can use the optional ``seqrepo_local_populator`` service.

This service is commented out by default. To enable this pattern:

1. Comment out the ``seqrepo`` service.
2. Uncomment ``seqrepo_local_populator``.
3. Adjust the ``rsync`` command if your snapshot directory name is different from ``2024-12-20``.
4. Change the ``depends_on`` for ``anyvar`` to depend on ``seqrepo_local_populator`` instead of ``seqrepo``:

   .. code-block:: yaml

      anyvar:
        depends_on:
          anyvar_db:
            required: true
            condition: service_started
          seqrepo_local_populator:
            required: true
            condition: service_completed_successfully

5. Export ``SEQREPO_ROOT_DIR`` before running compose:

   .. code-block:: bash

      export SEQREPO_ROOT_DIR=/path/to/my/seqrepo
      docker compose up

On startup, the ``seqrepo_local_populator`` container will copy your local SeqRepo snapshot into ``seqrepo_vol``. The ``anyvar`` container will then use the volume just as in the default configuration.

UTA Service Configuration
-------------------------

The ``uta`` service runs a UTA PostgreSQL instance with its data directory on the ``uta_vol`` volume.

You can test that UTA is running and populated by using the example ``psql`` command in the compose file comments.

AnyVar Database Configuration
-----------------------------

The ``anyvar_db`` service runs PostgreSQL and mounts ``anyvar_vol``. If you expose the AnyVar API publicly, you **must** change these defaults to secure values.

Running the stack
-----------------

After creating the external volumes and configuring any optional environment variables (such as ``SEQREPO_ROOT_DIR``), you can start the stack with:

.. code-block:: bash

   docker compose up

The AnyVar API will be available on ``http://127.0.0.1:8010`` by default, under the ``ports`` mapping.
