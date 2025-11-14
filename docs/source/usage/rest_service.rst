Running REST Service
!!!!!!!!!!!!!!!!!!!!

Spinning Up the REST Server
===========================

AnyVar uses `FastAPI <https://fastapi.tiangolo.com/>`_ to declare and provide REST-like HTTP service for registering and retrieving variant data. From an environment containing an AnyVar installation, launch service like so:

.. code-block:: console

   % uvicorn anyvar.restapi.main:app

See the `uvicorn docs <https://uvicorn.dev/settings/#configuration-methods>`_ or run ``uvicorn --help`` for more information.


Stateless Annotation and Translation
====================================

For cases where AnyVar's variant translation and VCF annotation services are sufficient, and no object storage is required, set the environment variable ``ANYVAR_STORAGE_URI`` to a blank value (i.e. an empty string). This utilizes the :py:class:`NoObjectStore <anyvar.storage.no_db.NoObjectStore>` class in place of a relational data backend.

.. code-block:: console

   % ANYVAR_STORAGE_URI="" uvicorn anyvar.restapi.main:app
