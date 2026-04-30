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

AnyVar implements a :py:mod:`Translator <anyvar.translate.base>` abstraction that can be used to ingest free-text variation expressions of known nomenclatures. By way of the `VRS-Python <https://github.com/ga4gh/vrs-python>`_ translator module, the following kinds of expressions are supported:


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

.. _extensions:

Object Extensions
=================

Registered variation objects can be associated with **extensions**, which provide a flexible mechanism for attaching additional, lightweight metadata to a variation. An extension consists of: a **name** (``str``), describing the type of metadata, and a **value**, which may be any JSON-serializable object.

Extensions are intended to mirror the concept of extensions in VRS: they capture auxiliary information that is closely associated with the variation itself, but not part of its core, identity-defining representation. Extensions are deliberately unstructured and permissive in order to support a wide range of use cases without requiring schema changes.

Examples of appropriate uses include:

- registration metadata (e.g., timestamps, provenance identifiers)
- cross-references to external resources
- links to associated samples, patients, or datasets
- simple flags or attributes relevant to the stored object

.. note::

   Extensions are **not** intended for storing large, complex, or highly
   interpretive data. In particular, they should not be used for:

   - detailed evidence or annotation records
   - clinical interpretations or assertions
   - large structured payloads or documents

   Such information is better represented in dedicated data models or external systems.

.. _mappings:

Variant Mappings
================

**Mappings** can be used to register specific modes of relationship between variations, such as reference assembly liftover. The :py:class:`VariationMappingType<anyvar.core.metadata.VariationMappingType>` enum provides the supported kinds of relationships:

.. autoclass:: anyvar.core.metadata.VariationMappingType
   :no-index:
   :members:
   :undoc-members:

.. _stateless_mode:

Stateless Mode
==============

Optionally, an AnyVar server can be configured as `stateless`, to provide its variant translation and bulk file annotation functions without any persistent object registration backend. This utilizes the :py:class:`NoObjectStore <anyvar.storage.no_db.NoObjectStore>` class in place of a relational data backend.
