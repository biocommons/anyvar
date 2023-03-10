.. _storage:

Storage Options
===============

AnyVar comes packaged with several options for storing variations. To select a storage option at startup, set the environment variable ``ANYVAR_STORAGE_URI`` to an appropriate value. If this variable is unset, the server will default to in-memory storage.

PostgreSQL
----------

`PostgreSQL <https://www.postgresql.org/>`_ is a popular SQL database system, and is our recommended storage solution for persistent and flexible searching capabilities. To enable, use a `libpq-compliant connection URI <https://www.postgresql.org/docs/current/libpq-connect.html#LIBPQ-CONNSTRING>`_, e.g.: ::

    export ANYVAR_STORAGE_URI=postgresql://postgres@localhost:5432/anyvar

Redis
-----

`Redis <https://redis.io/>`_ is a persistent key-value store that operates on data in-memory for heightened performance. To enable, provide a URI containing Redis credentials: ::

    export ANYVAR_STORAGE_URI=redis://[[username]:[password]]@localhost:6379/0

Shelve
------

`Shelve <https://docs.python.org/3/library/shelve.html>`_ is a persistent key-value store included in the Python3 standard library. To enable, provide a URI containing a path to a DB file: ::

    export ANYVAR_STORAGE_URI=file:///full/path/to/filename.db
    # or
    export ANYVAR_STORAGE_URI=full/path/to/filename.db

In-Memory
---------

Ideal for quick demoing or debugging, this option stores submitted variations within memory during the Python runtime. Critically, this means that all data is lost once the server process is ended. To enable, use the following storage URI: ::

    export ANYVAR_STORAGE_URI=memory:


