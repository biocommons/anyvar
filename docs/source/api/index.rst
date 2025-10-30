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
   anyvar.queueing.celery_worker
   anyvar.extras.vcf

Storage
=======

.. autosummary::
   :nosignatures:
   :toctree: api/storage/
   :template: module_summary.rst

   anyvar.storage.base_storage
   anyvar.storage.postgres
   anyvar.storage.mapper_registry
   anyvar.storage.mappers
   anyvar.storage.orm
   anyvar.storage.no_db

Translate
=========

.. autosummary::
   :nosignatures:
   :toctree: api/translate/
   :template: module_summary.rst

   anyvar.translate.translate
   anyvar.translate.vrs_python

Utilities
=========

.. autosummary::
   :nosignatures:
   :toctree: api/utils/
   :template: module_summary.rst

   anyvar.utils.funcs
   anyvar.utils.liftover_utils
   anyvar.utils.types
