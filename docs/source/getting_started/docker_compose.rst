Quick Setup: Docker Compose
!!!!!!!!!!!!!!!!!!!!!!!!!!!

Prerequisites
=============

* `Docker Compose <https://docs.docker.com/compose/install/>`_

Steps
=====

AnyVar provides a ready-to-use Docker Compose configuration that launches all required services: SeqRepo, UTA, the AnyVar database, and the AnyVar REST service itself. This is the fastest way to get a fully functional instance running for local development or evaluation.

Clone the AnyVar repository (optionally switching to a release tag), and enter the directory:

.. code-block:: console

   % git clone https://github.com/biocommons/anyvar
   % cd anyvar

Create all required volumes:

.. code-block:: bash

   % docker volume create seqrepo_vol
   % docker volume create uta_vol
   % docker volume create anyvar_vol

Then, launch the application:

.. code-block:: console

   % docker compose up

This will:

* pull the necessary images,
* start SeqRepo (or use your local SeqRepo if configured),
* start UTA and AnyVar’s PostgreSQL database,
* and launch AnyVar REST service.

Once the containers are running, visit `http://127.0.0.1:8010/docs <http://127.0.0.1:8010/docs>`_ to view the interactive Swagger UI and confirm the service is responding.

See :doc:`REST API usage <../usage/rest_api>` for supported server functions and endpoints, and :doc:`Configuring Docker Compose <../configuration/docker_compose>` for more configuration information.
