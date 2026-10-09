.. _api_reference:

API Reference
!!!!!!!!!!!!!

Core Functions and Utilities
============================

.. autosummary::
   :nosignatures:
   :toctree:
   :template: module_summary.rst

   anyvar.anyvar
   anyvar.core.metadata
   anyvar.core.objects
   anyvar.core.categorical_variants

VCF Ingestion
=============

.. autosummary::
   :nosignatures:
   :toctree: vcf
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
   :toctree: storage/
   :template: module_summary_no_inherit.rst

   anyvar.storage.base
   anyvar.storage.postgres
   anyvar.storage.duckdb
   anyvar.storage.mapper_registry
   anyvar.storage.mappers
   anyvar.storage.orm
   anyvar.storage.no_db

Variant Translation
===================

.. autosummary::
   :nosignatures:
   :toctree: translate/
   :template: module_summary.rst

   anyvar.translate.base
   anyvar.translate.vrs_python
   anyvar.translate.register

Mapping
=======

.. autosummary::
   :nosignatures:
   :toctree: mapping/
   :template: module_summary.rst

   anyvar.mapping.liftover
   anyvar.mapping.projection_models
   anyvar.mapping.projection
   anyvar.mapping.protocols
