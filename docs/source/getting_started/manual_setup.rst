Manual Setup
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

More advanced users may want to tailor resources to their specific needs. This section provides all required steps for a complete manual setup, but is intentionally high-level because user needs may vary depending on use cases.

Prerequisites
=============

* Python >= 3.10
* PostgreSQL
* Redis, or another `Celery backend/broker <https://docs.celeryq.dev/en/stable/getting-started/backends-and-brokers/index.html>`_

Python Package
==============

.. TODO update once available on PyPI -- see issue #138

Install AnyVar from the GitHub repository:

.. code-block:: console

   % python -m pip install git+https://github.com/biocommons/anyvar

Activate a virtual environment, and install AnyVar with optional dependencies for PostgreSQL storage and task queueing:

.. code-block:: console

   % python -m pip install ".[postgres,queueing]"

Storage Backend: PostgreSQL Service
===================================

Most AnyVar users will require persistent variation storage, which is supported via a PostgreSQL database. See the `PostgreSQL docs <https://www.postgresql.org/docs/current/tutorial-install.html>`_ for installation suggestions.

AnyVar utilizes the connection string defined by the environment variable ``ANYVAR_STORAGE_URI`` to instantiate a connection to the PostgreSQL instance. The user and database declared in this string must be created manually. For example:

.. code-block:: console

   % psql -U postgres -C "CREATE USER anyvar WITH PASSWORD 'anyvar-pw'; CREATE DATABASE anyvar WITH OWNER anyvar;"
   % export ANYVAR_STORAGE_URI="postgresql://anyvar:anyvar-pw@localhost:5432/anyvar"

See more on storage configuration :doc:`here <../configuration/storage>`.

Data Resource: UTA
==================

UTA provides transcript- and alignment-level data used by AnyVar.

For installation and maintenance instructions, see the UTA documentation:

* **Install with Docker (preferred)** — a prebuilt PostgreSQL image with UTA data ready to run:
  https://github.com/biocommons/uta?tab=readme-ov-file#installing-with-docker-preferred

* **Install from database dumps** — instructions for loading UTA data into your own PostgreSQL instance:
  https://github.com/biocommons/uta?tab=readme-ov-file#installing-from-database-dumps

Data Resource: SeqRepo
======================

SeqRepo provides local, versioned access to reference sequences.

For setup options, see the SeqRepo documentation and Docker image:

* **Install within Python** — using ``seqrepo`` as a local sequence resource from a Python environment:
  https://github.com/biocommons/biocommons.seqrepo?tab=readme-ov-file#all-platforms

* **Docker image** — a containerized SeqRepo dataset suitable for use with AnyVar and other tools:
  https://hub.docker.com/r/biocommons/seqrepo

Queueing Backend/Broker: Redis
==============================

Task queueing for operations on large VCFs requires the availability of a backend and broker for Celery. Most users are recommended to use `Redis <https://redis.io/docs/latest/>`. For example, to launch a Redis docker container:

.. code-block:: console

   % docker run -d --name redis -p 6379:6379 redis:latest

Verifying Installation
======================

Launch the REST API server:

.. code-block:: console

   % python -m uvicorn anyvar.restapi.main:app

...and direct your web browser to `http://127.0.0.1 <http://127.0.0.1>`. You should see the Swagger UI documentation demonstrating AnyVar REST API endpoints.
