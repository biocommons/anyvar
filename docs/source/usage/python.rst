.. _python_usage:

Using the Python API
!!!!!!!!!!!!!!!!!!!!

This page demonstrates basic usage of the AnyVar Python interface. See the :ref:`Python API reference <API_Reference>` for a more exhaustive description of public functions and classes.


.. note::

   For brevity, some code samples assume variables or setup defined earlier on the page.

Instantiating An AnyVar Instance
================================

The :py:class:`~anyvar.anyvar.AnyVar` class requires implementation of the :py:class:`~anyvar.storage.base_storage.Storage` and :py:class:`~anyvar.translate.translate._Translator` abstractions. These can easily be instantiated with the :py:meth:`~anyvar.anyvar.create_storage` and :py:meth:`~anyvar.anyvar.create_translator` factory functions:

.. code-block:: pycon

   >>> from anyvar.anyvar import AnyVar, create_storage, create_translator
   >>> av = AnyVar(create_translator(), create_storage())

Basic Variant Object Operations
===============================

Use the :py:meth:`anyvar.anyvar.AnyVar.put_objects` method to add :ref:`supported objects <supported-variant-data-types>`, such as VRS alleles.

.. code-block:: pycon

   >>> from ga4gh.vrs import models
   >>> allele = models.Allele(**{
   ...     "id": "ga4gh:VA.K7akyz9PHB0wg8wBNVlWAAdvMbJUJJfU",
   ...     "digest": "K7akyz9PHB0wg8wBNVlWAAdvMbJUJJfU",
   ...     "location": {
   ...         "id": "ga4gh:SL.aCMcqLGKClwMWEDx3QWe4XSiGDlKXdB8",
   ...         "digest": "aCMcqLGKClwMWEDx3QWe4XSiGDlKXdB8",
   ...         "end": 87894077,
   ...         "start": 87894076,
   ...         "sequenceReference": {
   ...             "refgetAccession": "SQ.ss8r_wB0-b9r44TQTMmVTI92884QvBiB",
   ...             "type": "SequenceReference"
   ...         },
   ...         "type": "SequenceLocation"
   ...     },
   ...     "state": {
   ...         "sequence": "T",
   ...         "type": "LiteralSequenceExpression"
   ...     },
   ...     "type": "Allele"
   ... })
   >>> av.put_objects([allele])

Retrieve variation objects by ID:

.. code-block:: pycon

   >>> av.get_object("ga4gh:VA.K7akyz9PHB0wg8wBNVlWAAdvMbJUJJfU")
   Allele(id='ga4gh:VA.K7akyz9PHB0wg8wBNVlWAAdvMbJUJJfU', type='Allele', name=None, description=None, aliases=None, extensions=None, digest='K7akyz9PHB0wg8wBNVlWAAdvMbJUJJfU', expressions=None, location=SequenceLocation(id='ga4gh:SL.01EH5o6V6VEyNUq68gpeTwKE7xOo-WAy', type='SequenceLocation', name=None, description=None, aliases=None, extensions=None, digest='01EH5o6V6VEyNUq68gpeTwKE7xOo-WAy', sequenceReference=SequenceReference(id=None, type='SequenceReference', name=None, description=None, aliases=None, extensions=None, refgetAccession='SQ.ss8r_wB0-b9r44TQTMmVTI92884QvBiB', residueAlphabet=None, circular=None, sequence=None, moleculeType=None), start=87894076, end=87894077, sequence=None), state=LiteralSequenceExpression(id=None, type='LiteralSequenceExpression', name=None, description=None, aliases=None, extensions=None, sequence=sequenceString(root='T')))

When an object is registered, any objects contained within it are also registered. They may similarly be retrieved:

.. code-block:: pycon

   >>> av.get_object("ga4gh:SL.aCMcqLGKClwMWEDx3QWe4XSiGDlKXdB8")
   SequenceLocation(id='ga4gh:SL.aCMcqLGKClwMWEDx3QWe4XSiGDlKXdB8', type='SequenceLocation', name=None, description=None, aliases=None, extensions=None, digest='aCMcqLGKClwMWEDx3QWe4XSiGDlKXdB8', sequenceReference=SequenceReference(id=None, type='SequenceReference', name=None, description=None, aliases=None, extensions=None, refgetAccession='SQ.ss8r_wB0-b9r44TQTMmVTI92884QvBiB', residueAlphabet=None, circular=None, sequence=None, moleculeType=None), start=87894076, end=87894077, sequence=None)

Variation Translation
=====================

AnyVar's :ref:`variation translation <supported-variant-nomenclature>` feature can be used to construct supported input objects from other representational nomenclatures. For example, to register a variant using `HGVS nomenclature <https://hgvs-nomenclature.org/stable/>`_:

.. code-block:: pycon

   >>> av = AnyVar(create_translator(), create_storage())
   >>> braf_variant = av.translator.translate_allele("NM_004333.6:c.1799T>A")
   >>> braf_variant.id
   'ga4gh:VA.XbRlw94yRqkcqY59FKba99Lsd1oc5AE_'
   >>> av.put_objects([braf_variant])

Variation Liftover
==================

AnyVar employs the `agct <https://github.com/GenomicMedLab/agct/>`_ library to lift genomic variation locations between equivalent positions on GRCh37 and GRCh38. The :py:func:`~anyvar.utils.liftover_utils.get_liftover_variant` function takes a variation, determines its reference assembly, and returns the corresponding allele on the opposite assembly.

.. code-block:: pycon

   >>> from anyvar.utils.liftover_utils import get_liftover_variant
   >>> (allele.location.start, allele.location.end)
   (87894076, 87894077)
   >>> lifted_variant = get_liftover_variant(allele)
   >>> (lifted_variant.location.start, lifted_variant.location.end)
   (89653833, 89653834)

Object Mappings
===============

AnyVar can add basic mappings between objects with :py:meth:`AnyVar.put_mapping() <anyvar.anyvar.AnyVar.put_mapping>`.

.. code-block:: pycon

   >>> from anyvar.utils.types import VariationMapping, VariationMappingType
   >>> genomic_allele = av.translator.translate_allele("NC_000007.14:g.140753336A>T")
   >>> tx_allele = av.translator.translate_allele("NM_004333.6:c.1799T>A")
   >>> av.put_objects([genomic_allele, tx_allele])
   >>> mapping = VariationMapping(
   ...     source_id=genomic_allele.id,
   ...     dest_id=tx_allele.id,
   ...     mapping_type=VariationMappingType.TRANSCRIPTION
   ... )
   >>> av.put_mapping(mapping)

They can be retrieved with :py:meth:`AnyVar.get_object_mappings() <anyvar.anyvar.AnyVar.get_object_mappings>`.

.. code-block:: pycon

   >>> av.get_object_mappings(genomic_allele.id, VariationMappingType.TRANSCRIPTION)
   [VariationMapping(source_id='ga4gh:VA.Otc5ovrw906Ack087o1fhegB4jDRqCAe', dest_id='ga4gh:VA.W6xsV-aFm9yT2Bic5cFAV2j0rll6KK5R', mapping_type=<VariationMappingType.TRANSCRIPTION: 'transcription'>)]

See :ref:`here <mappings>` for more information about object mappings in AnyVar.

The :py:mod:`~anyvar.utils.liftover_utils` module provides the :py:func:`~anyvar.utils.liftover_utils.add_liftover_mapping` function as a convenient way to find the lifted-over equivalent of a variation, register it, and add mappings of type ``liftover`` between them.

Object Annotations
==================

AnyVar can apply basic annotations on objects with :py:meth:`AnyVar.put_annotation() <anyvar.anyvar.AnyVar.put_annotation>`.

.. code-block:: pycon

   >>> from anyvar.utils.types import Annotation
   >>> av.put_annotation(Annotation(
   ...     object_id=genomic_allele.id,
   ...     annotation_type="clinvar_somatic_classification",
   ...     annotation_value="Oncogenic"
   ... ))
   >>> av.put_annotation(Annotation(
   ...     object_id=genomic_allele.id,
   ...     annotation_type="associated_pmids",
   ...     annotation_value=["21639808", "31566309", "27283860"]
   ... ))

Annotations can be retrieved with :py:meth:`AnyVar.get_object_annotations <anyvar.anyvar.AnyVar.get_object_annotations>` using the object ID, and optionally the provided annotation type.

.. code-block:: pycon

   >>> av.get_object_annotations(genomic_allele.id)
   [Annotation(object_id='ga4gh:VA.Otc5ovrw906Ack087o1fhegB4jDRqCAe', annotation_type='clinvar_somatic_classification', annotation_value='Oncogenic'),
    Annotation(object_id='ga4gh:VA.Otc5ovrw906Ack087o1fhegB4jDRqCAe', annotation_type='associated_pmids', annotation_value=['21639808', '31566309', '27283860'])]
   >>> av.get_object_annotations(genomic_allele.id, "associated_pmids")
   [Annotation(object_id='ga4gh:VA.Otc5ovrw906Ack087o1fhegB4jDRqCAe', annotation_type='associated_pmids', annotation_value=['21639808', '31566309', '27283860'])]

See :ref:`here <annotations>` for more information about object annotations in AnyVar.

VCF Ingest and Annotation
=========================

AnyVar can consume a Variant Call Format (VCF) file, register all contained variants, and return a copy annotated with variant IDs for later lookup.

.. code-block:: pycon

   >>> from anyvar.extras.vcf import VcfRegistrar
   >>> from pathlib import Path
   >>> registrar = VcfRegistrar(data_proxy=av.translator.dp, av=av)
   >>> registrar.annotate(Path("my_vcf.vcf"), Path("out.vcf"))
