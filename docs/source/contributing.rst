Contributing to AnyVar
!!!!!!!!!!!!!!!!!!!!!!

Installing For Development
==========================

Clone and enter the repo, use the ``devready`` Makefile target to set up a virtual environment, then activate it and install pre-commit hooks:

.. code-block:: shell

    git clone https://github.com/biocommons/anyvar.git
    cd anyvar
    make devready
    source venv/3.11/bin/activate
    pre-commit install

Testing
=======

Some configuration is required to run tests:

* **Install test dependencies** - in your AnyVar environment, ensure that the ``test`` dependency group is available by running ``make testready`` in the root directory.
* **Configure test database** - unit and integration tests will set up a storage instance using the connection string defined by the environment variable ``ANYVAR_TEST_STORAGE_URI`` (not ``ANYVAR_STORAGE_URI``!), which defaults to ``"postgresql://postgres:postgres@localhost:5432/anyvar_test"``.

.. note::

    Ensure that the database and role are available in the PostgreSQL instance.

    For example, to support the connection string ``"postgresql://anyvar_test_user:anyvar_test_pw@localhost:5432/anyvar_test_db"``, run ``psql -U postgres -C "CREATE USER anyvar_test_user WITH PASSWORD anyvar_test_pw; CREATE DATABASE anyvar_test_db WITH OWNER anyvar_test_user;"``

* **Ensure Celery backend and broker are available, and that Celery workers are NOT running** - the task queueing tests create and manage their own Celery workers, but they do require access to a broker/backend for message transport and result storage. See `async task queuing setup instructions <todo>`_ for more. If an existing AnyVar Celery worker is running, they may not function properly.

.. TODO fix celery reference above

Tests are invoked with the ``pytest`` command. The project Makefile includes an easy shortcut:

.. code-block:: shell

   make test

Documentation
=============

To build documentation, use the ``docs`` Makefile target from the project root directory:

.. code-block::

   make docs

HTML output is built in the subdirectory ``docs/build/html/``.

The docs use `Sphinx GitHub Changelog <https://github.com/ewjoachim/sphinx-github-changelog>`_ to automatically generate the :doc:`changelog <changelog>` page. A GitHub API token must be provided for the Sphinx build process to fetch GitHub release history and generate this page. If not provided, an error will be logged during the build and the page will be blank.
