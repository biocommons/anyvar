.. _rest_service_usage:

Running REST Service
!!!!!!!!!!!!!!!!!!!!

Spinning Up the REST Server
===========================

AnyVar uses `FastAPI <https://fastapi.tiangolo.com/>`_ to provide a REST-style HTTP interface for registering and retrieving variant data. In an environment where AnyVar is installed, you can start the server with:

.. code-block:: console

   % python -m uvicorn anyvar.restapi.main:app

See the `uvicorn documentation <https://uvicorn.dev/settings/#configuration-methods>`_ or run ``uvicorn --help`` for additional options.

Once the server is running, most endpoints work immediately. However, operations that require asynchronous background processing—such as handling VCF input—also need a running `Celery <https://docs.celeryq.dev/en/v5.5.3/index.html>`_ worker:

.. code-block:: console

   % python -m celery -A anyvar.queueing.celery_worker:celery_app worker

Storing Environment Variables
=============================

The AnyVar FastAPI app uses `python-dotenv <https://saurabh-kumar.com/python-dotenv/>`_ to load environment variables from a ``.env`` file when launched. See :doc:`the example file <../configuration/dotenv_example>` for a starting point.

Stateless Annotation and Translation
====================================

To use AnyVar in :ref:`stateless mode<stateless_mode>`, set the environment variable ``ANYVAR_STORAGE_URI`` to a blank value (i.e. an empty string).

.. code-block:: console

   % ANYVAR_STORAGE_URI="" uvicorn anyvar.restapi.main:app
