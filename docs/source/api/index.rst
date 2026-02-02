.. _api_reference:

API Reference
!!!!!!!!!!!!!

Core Functions and Utilities
============================

.. autosummary::
   :nosignatures:
   :toctree: api/
   :template: module_summary.rst

   anyvar.anyvar
   anyvar.core.metadata
   anyvar.core.objects

VCF Ingestion
=============

.. autosummary::
   :nosignatures:
   :toctree: api/vcf
   :template: module_summary.rst

   anyvar.vcf.ingest


Bulk Processing
===============

.. autosummary::
   :nosignatures:
   :toctree: api/queueing
   :template: module_summary.rst

   anyvar.queueing.celery_worker

Object Storage
==============

.. autosummary::
   :nosignatures:
   :toctree: api/storage/
   :template: module_summary_no_inherit.rst

   anyvar.storage.base
   anyvar.storage.postgres
   anyvar.storage.mapper_registry
   anyvar.storage.mappers
   anyvar.storage.orm
   anyvar.storage.no_db

Variant Translation
===================

.. autosummary::
   :nosignatures:
   :toctree: api/translate/
   :template: module_summary.rst

   anyvar.translate.base
   anyvar.translate.vrs_python

Mapping
=======

.. autosummary::
   :nosignatures:
   :toctree: api/mapping/
   :template: module_summary.rst

   anyvar.mapping.liftover
