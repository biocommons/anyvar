.. _quick-start:

Quick Start
!!!!!!!!!!!

Installation and Service Initialization
=======================================

.. TODO this should obviously just be about installing from pypi

Clone the AnyVar repository
---------------------------

::

   git clone https://github.com/biocommons/anyvar
   cd anyvar

.. TODO presumably something about virtual env/installation? use the makefile?

Set Environment Variables
-------------------------

Create a ``.env`` file in the repo root to store environment configurations. ::

   touch .env

See the :ref:`example configuration <example-config>` file for a complete description of available configurations.

Initialize Storage
------------------

Most nontrivial uses of AnyVar will require the initialization of a storage backend. See the following for option-specific setup instructions:

* :ref:`PostgreSQL <postgresql-setup>`
* :ref:`Snowflake <snowflake-setup>`

AnyVar can also be run without a database. This is primarily useful for bulk VCF annotations where there is no need to reuse previously-computed VRS IDs. To do so, set the ``ANYVAR_STORAGE_URI`` environment variable to an empty string (`""`) in your ``.env`` file, i.e. with ``echo "ANYVAR_STORAGE_URI=" >> .env``.

Configure Required Dependencies
-------------------------------

AnyVar relies on a handful of data services to provide sequence translation and storage. If they are not already available on your system, they must be initialized prior to launching an AnyVar service.

* SeqRepo stores biological sequence data and can be accessed locally or via REST API. :ref:`Read how to set up SeqRepo locally or through Docker <seqrepo-setup>`.

* UTA (Universal Transcript Archive) stores transcripts aligned to sequence references. :ref:`Read how to set up UTA locally or via Docker <uta-setup>`.

Configure Asynchronous Operations (Optional)
--------------------------------------------

AnyVar supports asynchronous VCF annotation for improved scalability. :ref:`See asynchronous operations instructions <async>`.

Start the AnyVar Server
-----------------------

::

   uvicorn anyvar.restapi.main:app --reload

Visit `http://localhost:8000 <http://localhost:8000>`_ to verify the REST API is running.
