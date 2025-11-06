Features
!!!!!!!!

.. _supported-variant-data-types:

Variant Object Types
====================

* VRS Allele
* VRS SequenceLocation
* VRS SequenceReference


.. _supported-variant-nomenclature:

Variant Translation
===================

* HGVS
* SPDI
* GNOMAD VCF

.. _annotations:

Object Annotations
==================

Registered variants can be associated with **annotations**. Annotations consist of a **type**, of type ``str``, and a **value**,

.. autoclass:: anyvar.utils.types.Annotation
   :no-index:
   :members:
   :undoc-members:
   :special-members: __init__
   :exclude-members: model_fields, model_config

.. _mappings:

Variant Mappings
================

.. maybe embed mapping class here?
