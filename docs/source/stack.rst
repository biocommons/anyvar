The AnyVar Stack
================

AnyVar relies upon a number of services and data sources to provide complete translation and digestion.

Storage backend
---------------

AnyVar is capable of interfacing with several different storage solutions out-of-the-box. See the :doc:`storage <./storage>` documentation for more info.

Variation representation
------------------------

Variation objects are structured and stored in adherence with version 1.2 of the `GA4GH Variation Representation Specification <https://vrs.ga4gh.org/en/stable/>`_. Support for classes described in later VRS versions is :doc:`planned <./roadmap>`.

Input normalization
--------------------------------

Provided variations may undergo extensive translation, normalization, and validation before storage to ensure correctness and consistency. Currently, AnyVar employs the `VICC Variation Normalizer <https://github.com/cancervariants/variation-normalization/>`_ as normalization middleware to convert free-text variation descriptions into structured objects.

Universal Transcript Archive (UTA)
----------------------------------

The `Universal Transcript Archive (UTA) <https://github.com/biocommons/uta>`_, provides aligned transcripts and references sequences. The Variation Normalizer uses UTA to identify and select from transcripts that are compatible with a user-provided variation.

SeqRepo
-------

The Variation Normalizer also uses a `SeqRepo <https://www.ncbi.nlm.nih.gov/pmc/articles/PMC7714221/>`_ instance to identify sequences and sequence aliases. Additionally, SeqRepo's sha412t24u identification algorithm is used to generate keys for Alleles, Sequence Locations, and other objects stored by AnyVar.
