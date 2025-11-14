Contributing to AnyVar
!!!!!!!!!!!!!!!!!!!!!!

Installing For Development
==========================

Clone and enter the repo, use the `devready` Makefile target to set up a virtual environment, then activate it and install pre-commit hooks:

.. code-block:: shell

    git clone https://github.com/biocommons/anyvar.git
    cd anyvar
    make devready
    source venv/3.11/bin/activate
    pre-commit install

Testing
=======

.. TODO test DB setup commands?

As initial AnyVar development is ongoing, running all tests requires a small amount of upfront configuration.

* ``Install test dependencies`` - in your AnyVar environment, ensure that the ``test`` dependency group is available by running ``make testready`` in the root directory.
* ``Configure test database`` - unit and integration tests will set up a storage instance using the connection string defined by the environment variable ``ANYVAR_TEST_STORAGE_URI``, which defaults to ``"postgresql://postgres:postgres@localhost:5432/anyvar_test"``.
* ``Ensure Celery backend and broker are available, and that Celery workers are NOT running`` - the task queueing tests create and manage their own Celery workers, but they do require access to a broker/backend for message transport and result storage. See `async task queuing setup instructions <todo>`_ for more. If an existing AnyVar Celery worker is running, they may not function properly.

Tests are invoked with the ``pytest`` command. The project Makefile includes an easy shortcut:

.. code-block:: shell

   make test

Documentation
=============

To build documentation, use the ``docs`` Makefile target from the project root directory:

.. code-block::

   make docs

HTML output is built in the subdirectory ``docs/build/html/``.
