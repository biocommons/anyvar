REST API Usage
!!!!!!!!!!!!!!

AnyVar can be interacted with via HTTP requests.

Swagger UI Docs
===============

An AnyVar server hosts Swagger UI documentation at the server root address (e.g. `http://localhost:8000 <http://localhost:8000>`_ by default in the context of local service). This page lists all API routes, includes schemas describing valid request and response structures, and an easy-to-use interface to test out API calls.

Basic Variant Operations
========================

Send a ``PUT`` request to ``/variation`` with a payload containing a variant definition using a :ref:`supported variant definition nomenclature<supported-variant-nomenclature>`. If translation and registration are successful, the response will include the variant's `identifier <https://vrs.ga4gh.org/en/stable/conventions/computed_identifiers.html>`_ and the complete `VRS allele object <https://vrs.ga4gh.org/en/stable/concepts/MolecularVariation/Allele.html>`_.

.. code-block:: pycon

   >>> import requests
   >>> payload = {"definition": "NC_000010.11:g.87894077C>T"}
   >>> response = requests.put("http://localhost:8000/variation", json=payload)
   >>> allele_id = response.json()["object_id"]
   >>> allele_id
   'ga4gh:VA.K7akyz9PHB0wg8wBNVlWAAdvMbJUJJfU'
   >>> response.json()["object"]
   {'id': 'ga4gh:VA.K7akyz9PHB0wg8wBNVlWAAdvMbJUJJfU', 'type': 'Allele', 'digest': 'K7akyz9PHB0wg8wBNVlWAAdvMbJUJJfU', 'location': {'id': 'ga4gh:SL.01EH5o6V6VEyNUq68gpeTwKE7xOo-WAy', 'type': 'SequenceLocation', 'digest': '01EH5o6V6VEyNUq68gpeTwKE7xOo-WAy', 'sequenceReference': {'type': 'SequenceReference', 'refgetAccession': 'SQ.ss8r_wB0-b9r44TQTMmVTI92884QvBiB'}, 'start': 87894076, 'end': 87894077}, 'state': {'type': 'LiteralSequenceExpression', 'sequence': 'T'}}

A ``GET`` request to ``/variation/<ID>`` can be used to retrieve the same object later.

.. code-block:: pycon

   >>> response = requests.get(f"http://localhost:8000/variation/{allele_id}")
   >>> response.json()["data"]
   {'id': 'ga4gh:VA.K7akyz9PHB0wg8wBNVlWAAdvMbJUJJfU', 'type': 'Allele', 'digest': 'K7akyz9PHB0wg8wBNVlWAAdvMbJUJJfU', 'location': {'id': 'ga4gh:SL.aCMcqLGKClwMWEDx3QWe4XSiGDlKXdB8', 'type': 'SequenceLocation', 'digest': 'aCMcqLGKClwMWEDx3QWe4XSiGDlKXdB8', 'sequenceReference': {'type': 'SequenceReference', 'refgetAccession': 'SQ.ss8r_wB0-b9r44TQTMmVTI92884QvBiB'}, 'start': 87894076, 'end': 87894077}, 'state': {'type': 'LiteralSequenceExpression', 'sequence': 'T'}}

Variant registration also registered contained VRS objects, like SequenceLocations and SequenceReferences. Those objects can be retrieved in a similar manner.

.. code-block:: pycon

   >>> location_id = "ga4gh:SL.01EH5o6V6VEyNUq68gpeTwKE7xOo-WAy"
   >>> response = requests.get(f"http://localhost:8000/variation/{location_id}")
   >>> response.json()["data"]
   {'id': 'ga4gh:SL.01EH5o6V6VEyNUq68gpeTwKE7xOo-WAy', 'type': 'SequenceLocation', 'digest': '01EH5o6V6VEyNUq68gpeTwKE7xOo-WAy', 'sequenceReference': {'type': 'SequenceReference', 'refgetAccession': 'SQ.ss8r_wB0-b9r44TQTMmVTI92884QvBiB'}, 'start': 87894076, 'end': 87894077}

Working With Mappings
=====================

TODO -- not supported yet

Working With Annotations
========================

To add a new :ref:`annotation<annotations>` to a registered variation, send a ``POST`` request to ``/variation/<vrs_id>/annotations`` with a payload containing the annotation type and value:

.. code-block:: pycon

   >>> payload = {
   ...     "annotation_type": "clinvar_somatic_classification",
   ...     "annotation_value": "Oncogenic",
   ... }
   >>> braf_v600e_id = "ga4gh:VA.K7akyz9PHB0wg8wBNVlWAAdvMbJUJJfU"
   >>> response = requests.post(f"http://localhost:8000/variation/{braf_v600e_id}/annotations", json=payload)

Annotations can be retrieved via a GET request for the VRS ID and annotation type:

.. code-block:: pycon

   >>> resp = requests.get(f"http://localhost:8000/variation/{braf_v600e_id}/annotations/clinvar_somatic_classification")
   >>> response.json()
   {'annotations': [{'object_id': 'ga4gh:VA.K7akyz9PHB0wg8wBNVlWAAdvMbJUJJfU', 'annotation_type': 'clinvar_somatic_classification', 'annotation_value': 'Oncogenic', 'id': 9}]}

VCF Annotation and Ingestion
============================



Variant Search
==============
