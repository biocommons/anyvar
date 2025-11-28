Features
!!!!!!!!

.. _supported-variant-data-types:

Variant Object Types
====================

AnyVar enables the registration and retrieval of a number of different variation object types, beginning with core elements of the `GA4GH Variation Representation Specification (VRS) <https://vrs.ga4gh.org/en/stable>`_:

* `VRS Allele <https://vrs.ga4gh.org/en/stable/concepts/MolecularVariation/Allele.html>`_
* `VRS SequenceLocation <https://vrs.ga4gh.org/en/stable/concepts/LocationAndReference/SequenceLocation.html>`_
* `VRS SequenceReference <https://vrs.ga4gh.org/en/stable/concepts/LocationAndReference/SequenceReference.html>`_

.. _supported-variant-nomenclature:

Variant Translation
===================

AnyVar implements a :py:mod:`Translator <anyvar.translate.translate>` abstraction that can be used to ingest free-text variation expressions of known nomenclatures. By way of the `VRS-Python <https://github.com/ga4gh/vrs-python>`_ translator module, the following kinds of expressions are supported:


.. list-table::
   :widths: 60 150
   :header-rows: 1

   * - Expression Type
     - Example
   * - HGVS
     - ``NC_000007.14:g.140753336A>T``
   * - SPDI
     - ``NC_000007.14:140753335:A:T``
   * - gnomAD/VCF
     - ``7-140753335-A-T``

.. _vcf_ingest:

VCF Ingestion and Annotation
============================

AnyVar can ingest and register all variants (and reference alleles) contained within a Variant Call Format (VCF) file, and return a file copy with variation IDs included as INFO field properties.

.. _annotations:

Object Annotations
==================

Registered variation objects can be associated with **annotations**. Annotations consist of a **type**, of type ``str``, and a **value**, which can be any JSON-serializable object or value. Annotations may be used to link to external references, indicate variant classifications, or otherwise adjoin genomic knowledge to a variation.

.. autoclass:: anyvar.utils.types.Annotation
   :no-index:
   :members:
   :undoc-members:
   :special-members: __init__
   :exclude-members: model_fields, model_config

.. _mappings:

Variant Mappings
================

**Mappings** can be used to register specific modes of relationship between variations, such as reference assembly liftover. The :py:class:`VariationMappingType<anyvar.utils.types.VariationMappingType>` enum provides the supported kinds of relationships:

.. autoclass:: anyvar.utils.types.VariationMappingType
   :no-index:
   :members:
   :undoc-members:

.. _stateless_mode:

Stateless Mode
==============

Optionally, an AnyVar server can be configured as `stateless`, to provide its variant translation and bulk file annotation functions without any persistent object registration backend. This utilizes the :py:class:`NoObjectStore <anyvar.storage.no_db.NoObjectStore>` class in place of a relational data backend.
