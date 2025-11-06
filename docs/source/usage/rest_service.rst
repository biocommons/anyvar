REST Service
!!!!!!!!!!!!

AnyVar uses `FastAPI <https://fastapi.tiangolo.com/>`_ to declare and provide REST-like HTTP service for registering and retrieving variant data. From an environment containing an AnyVar installation, launch service like so:

.. code-block:: shell

   uvicorn anyvar.restapi.main:app

See the `uvicorn docs <https://uvicorn.dev/settings/#configuration-methods>`_ or run ``uvicorn --help`` for more information.
