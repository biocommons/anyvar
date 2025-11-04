Contributing to AnyVar
!!!!!!!!!!!!!!!!!!!!!!

Prerequisites
=============

* Python >= 3.11
* `Docker <https://docs.docker.com/engine/install/>`_

Installing for development
==========================

.. code-block:: shell

    git clone https://github.com/biocommons/anyvar.git
    cd anyvar
    make devready
    source venv/3.11/bin/activate
    pre-commit install

Testing
=======

As initial AnyVar development is ongoing, running all tests requires a small amount of upfront configuration.

* ``Configure test database`` - most unit and integration tests will set up a storage instance using the connection string defined by the environment variable ``ANYVAR_TEST_STORAGE_URI``, which defaults to ``"postgresql://postgres:postgres@localhost:5432/anyvar_test"``. Ensure that the database and role defined in this string are initialized.
* ``Configure Celery worker database`` - when testing the Celery workers employed by the asynchronous request-response task framework, it's less simple to inject a storage class instance, so these tests will use the connection string defined by the main application environment variable ``ANYVAR_STORAGE_URI``, which defaults to ``"postgresql://postgres@localhost:5432/anyvar"``.
* ``Install test dependencies`` - in your AnyVar environment, ensure that the ``test`` dependency group is available by running ``make testready`` in the root directory.

Note that

6. Finally, run tests with the following command:

.. code-block:: shell

   make test

Notes
=====

Currently, there is some interdependency between test modules -- namely, tests that rely on reading data from storage assume that the data from ``test_variation`` has been uploaded. A pytest hook ensures correct test order, but some test modules may not be able to pass when run in isolation. By default, the tests will use a Postgres database installation.

For the ``tests/test_vcf::test_vcf_registration_async`` unit test to pass, a real broker and backend are required for Celery to interact with. Set the ``CELERY_BROKER_URL`` and ``CELERY_BACKEND_URL`` environment variables. The simplest solution is to run Redis locally and use that for both the broker and the backend, eg:

.. code-block::

    export CELERY_BROKER_URL="redis://"
    export CELERY_BACKEND_URL="redis://"


Documentation
=============

To build documentation, use the ``docs`` Makefile target from the project root directory:

.. code-block::

   make docs

HTML output is built in the subdirectory ``docs/build/html/index.html``.
