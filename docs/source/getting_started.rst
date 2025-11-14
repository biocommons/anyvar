Getting Started
!!!!!!!!!!!!!!!

Quick Setup: Docker Compose
===========================

docker-compose up

Manual Setup
==========================================

More advanced users may want to tailor resources to their specific needs. This section provides all required steps for a complete manual setup, but is intentionally high-level because user needs may vary depending on use cases.

Prerequisites
-------------

* Python >= 3.10
* PostgreSQL
* Redis, or another `Celery backend/broker <https://docs.celeryq.dev/en/stable/getting-started/backends-and-brokers/index.html>`_

Python Package
--------------

.. TODO update once available on PyPI -- see issue #138

Install AnyVar from the GitHub repository:

.. code-block:: console

   % python -m pip install git+https://github.com/biocommons/anyvar

Storage Backend: PostgreSQL Service
-----------------------------------

Most AnyVar users will require persistent variation storage, which is supported via a PostgreSQL database. See the `PostgreSQL docs <https://www.postgresql.org/docs/current/tutorial-install.html>`_ for installation suggestions.

AnyVar utilizes the connection string defined by the environment variable ``ANYVAR_STORAGE_URI`` to instantiate a connection to the PostgreSQL instance. The user and database declared in this string must be created manually. For example:

.. code-block:: console

   % psql -U postgres -C "CREATE USER anyvar WITH PASSWORD 'anyvar-pw'; CREATE DATABASE anyvar WITH OWNER anyvar;"
   % export ANYVAR_STORAGE_URI="postgresql://anyvar:anyvar-pw@localhost:5432/anyvar"

Data Resources: SeqRepo and UTA
-------------------------------

First, there must be an available instance of `Biocommons SeqRepo <https://github.com/biocommons/biocommons.seqrepo>`_ data.

* docker
* other

.. TODO note about SEQREPO_ROOT_DIR ?

Then UTA


Queueing Backend/Broker: Redis
------------------------------

.. code-block:: console

   % docker run -d --name redis -p 6379:6379 redis:<version>

https://redis.io/docs/latest/operate/oss_and_stack/install/install-stack/docker/
