.. _rest_api_usage:

Using the REST API
!!!!!!!!!!!!!!!!!!

AnyVar can be interacted with via HTTP requests.

Swagger UI Docs
===============

An AnyVar server hosts Swagger UI documentation at the server root address (e.g. `http://localhost:8000 <http://localhost:8000>`_ by default in the context of local service). This shows all API routes, includes schemas describing valid request and response structures, and an easy-to-use interface to test out API calls.

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

   >>> response = requests.get(f"http://localhost:8000/object/{allele_id}")
   >>> response.json()["data"]
   {'id': 'ga4gh:VA.K7akyz9PHB0wg8wBNVlWAAdvMbJUJJfU', 'type': 'Allele', 'digest': 'K7akyz9PHB0wg8wBNVlWAAdvMbJUJJfU', 'location': {'id': 'ga4gh:SL.aCMcqLGKClwMWEDx3QWe4XSiGDlKXdB8', 'type': 'SequenceLocation', 'digest': 'aCMcqLGKClwMWEDx3QWe4XSiGDlKXdB8', 'sequenceReference': {'type': 'SequenceReference', 'refgetAccession': 'SQ.ss8r_wB0-b9r44TQTMmVTI92884QvBiB'}, 'start': 87894076, 'end': 87894077}, 'state': {'type': 'LiteralSequenceExpression', 'sequence': 'T'}}

Variant registration also registered contained VRS objects, like SequenceLocations and SequenceReferences. Those objects can be retrieved in a similar manner.

.. code-block:: pycon

   >>> location_id = "ga4gh:SL.01EH5o6V6VEyNUq68gpeTwKE7xOo-WAy"
   >>> response = requests.get(f"http://localhost:8000/object/{location_id}")
   >>> response.json()["data"]
   {'id': 'ga4gh:SL.01EH5o6V6VEyNUq68gpeTwKE7xOo-WAy', 'type': 'SequenceLocation', 'digest': '01EH5o6V6VEyNUq68gpeTwKE7xOo-WAy', 'sequenceReference': {'type': 'SequenceReference', 'refgetAccession': 'SQ.ss8r_wB0-b9r44TQTMmVTI92884QvBiB'}, 'start': 87894076, 'end': 87894077}

Searching Variants
==================

The ``/search`` endpoint enables retrieval of all variants that overlap a provided interval:

.. code-block:: pycon

   >>> sequence_accession_id = "ga4gh:SQ.ss8r_wB0-b9r44TQTMmVTI92884QvBiB"
   >>> start, end = 87894070, 87894080
   >>> response = requests.get(f"http://localhost:8000/search?accession={sequence_accession_id}&start={start}&end={end}")
   >>> response.json()["variations"][0]
   {'id': 'ga4gh:VA.K7akyz9PHB0wg8wBNVlWAAdvMbJUJJfU',
    'type': 'Allele',
    'digest': 'K7akyz9PHB0wg8wBNVlWAAdvMbJUJJfU',
    'location': {'id': 'ga4gh:SL.aCMcqLGKClwMWEDx3QWe4XSiGDlKXdB8',
     'type': 'SequenceLocation',
     'digest': 'aCMcqLGKClwMWEDx3QWe4XSiGDlKXdB8',
     'sequenceReference': {'type': 'SequenceReference',
      'refgetAccession': 'SQ.ss8r_wB0-b9r44TQTMmVTI92884QvBiB'},
     'start': 87894076,
     'end': 87894077},
    'state': {'type': 'LiteralSequenceExpression', 'sequence': 'T'}}

Working With Mappings
=====================

To add a :ref:`mapping <mappings>` between previously-registered variation objects issue a ``PUT`` request to ``/variations/<vrs_id>/mappings``, where ``vrs_id`` is the ``source_id`` of the mapping object:

.. code-block:: pycon

   >>> payload = {"definition": "NC_000007.14:g.140753336A>T"}
   >>> response = requests.put("http://localhost:8000/variation", json=payload)
   >>> genomic_id = response.json()["object"]["id"]
   >>> payload = {"definition": "NM_004333.6:c.1799T>A"}
   >>> response = requests.put("http://localhost:8000/variation", json=payload)
   >>> tx_id = response.json()["object"]["id"]
   >>> payload = {"dest_id": tx_id, "mapping_type": "transcribe_to"}
   >>> requests.put(
   ...     f"http://localhost:8000/object/{genomic_id}/mappings",
   ...     json=payload
   ... )

Mappings from an object can be retrieved via ``GET /variations/<vrs_id>/mappings/<mapping_type>``:

.. code-block:: pycon

   >>> response = requests.get(
   ...     f"http://localhost:8000/object/{genomic_id}/mappings/transcribe_to"
   ... )
   >>> response.json()
   {'mappings': [{'source_id': 'ga4gh:VA.Otc5ovrw906Ack087o1fhegB4jDRqCAe',
      'dest_id': 'ga4gh:VA.W6xsV-aFm9yT2Bic5cFAV2j0rll6KK5R',
      'mapping_type': 'transcribe_to'}]}


By default, when a GRCh37 or GRCh38 variant is registered, the lifted-over equivalent is also registered, and mappings between them are stored.

.. code-block:: pycon

   >>> payload = {"definition": "NC_000010.11:g.87894077C>T"}
   >>> response = requests.put("http://localhost:8000/variation", json=payload)
   >>> registered_allele_id = response.json()["object_id"]
   >>> response = requests.get(
   ...     f"http://localhost:8000/object/{registered_allele_id}/mappings/liftover_to"
   ... )
   >>> response.json()
   {'mappings': [{'source_id': 'ga4gh:VA.K7akyz9PHB0wg8wBNVlWAAdvMbJUJJfU',
   'dest_id': 'ga4gh:VA.rQBlRht2jfsSp6TpX3xhraxtmgXNKvQf',
   'mapping_type': 'liftover_to'}]}


Working With Extensions
========================

To add a new :ref:`extension<extensions>` to a registered variation, send a ``POST`` request to ``/object/<vrs_id>/extensions`` with a payload containing the extension name and value:

.. code-block:: pycon

   >>> payload = {
   ...     "name": "clinvar_accession",
   ...     "value": "VCV000012345.6",
   ... }
   >>> braf_v600e_id = "ga4gh:VA.K7akyz9PHB0wg8wBNVlWAAdvMbJUJJfU"
   >>> response = requests.post(f"http://localhost:8000/object/{braf_v600e_id}/extensions", json=payload)

Extensions can be retrieved via a GET request for the VRS ID and extension name:

.. code-block:: pycon

   >>> resp = requests.get(f"http://localhost:8000/object/{braf_v600e_id}/extensions/clinvar_accession")
   >>> response.json()
   {'object': {'id': 'ga4gh:VA.K7akyz9PHB0wg8wBNVlWAAdvMbJUJJfU',
     'type': 'Allele',
     'digest': 'K7akyz9PHB0wg8wBNVlWAAdvMbJUJJfU',
     'location': {'id': 'ga4gh:SL.aCMcqLGKClwMWEDx3QWe4XSiGDlKXdB8',
      'type': 'SequenceLocation',
      'digest': 'aCMcqLGKClwMWEDx3QWe4XSiGDlKXdB8',
      'sequenceReference': {'type': 'SequenceReference',
       'refgetAccession': 'SQ.ss8r_wB0-b9r44TQTMmVTI92884QvBiB'},
      'start': 87894076,
      'end': 87894077},
     'state': {'type': 'LiteralSequenceExpression', 'sequence': 'T'}},
    'object_id': 'ga4gh:VA.K7akyz9PHB0wg8wBNVlWAAdvMbJUJJfU',
    'extension_name': 'clinvar_accession',
    'extension_value': 'VCV000012345.6'}

VCF Annotation and Ingestion
============================

AnyVar can perform bulk variant ingest operations on Variant Call Format (VCF) files.

Files submitted to the ``/vcf`` endpoint will be parsed for variants, which will be translated into VRS objects and stored, and a copy of the file with added VRS ID annotations is returned.

.. code-block:: pycon

   >>> with open("my_vcf.vcf", "rb") as f:
   ...     files = {"vcf": ("my_vcf.vcf", f, "text/plain")}
   ...     response = requests.put("http://localhost:8000/vcf", files=files)
   >>> response.raise_for_status()
   >>> "VRS_Allele_IDs" in response.text
   True

For larger files, a nontrivial amount of processing time may be required before the annotated file is ready to return. Users are advised to use the ``run_async`` parameter, which employs an `asynchronous request-response pattern <https://learn.microsoft.com/en-us/azure/architecture/patterns/async-request-reply>`_ to support multiple long-running tasks. In this model, when run requests are submitted, a run ID is returned. This ID can then be used to poll the server for the status of the task, responding with ``202 ACCEPTED`` if the task was submitted successfully, but is still in progress, and then returning the annotated file when it's ready.

.. code-block:: pycon

   >>> with open("big_vcf.vcf", "rb") as f:
   ...     files = {"vcf": ("big_vcf.vcf", f, "text/plain")}
   ...     response = requests.put("http://localhost:8000/vcf?enable_async=true", files=files)
   >>> print(response.json()["status_message"])
   'Run submitted. Check status at /vcf/05385087-78e2-44d4-8ecc-3ca74563c4b1'
   >>> run_id = response.json()["run_id"]
   >>> response = requests.get(f"http://localhost:8000/vcf/{run_id}")
   >>> response.status_code
   202
   >>> # keep requesting until `200 OK`
   >>> response = requests.get(f"http://localhost:8000/vcf/{run_id}")
   >>> response.status_code
   200
   >>> # this indicates the task is complete and the request includes the finished file
   >>> "VRS_Allele_IDs" in response.text
   True

.. _get_service_info:

Get Service Info
================

AnyVar implements the `GA4GH Service Info specification <https://www.ga4gh.org/product/service-info/>`_. Get information about the AnyVar instance and the data standards it employs at ``GET /service-info``:

.. code-block:: pycon

   >>> response = requests.get("http://localhost:8000/service-info")
   >>> response.json()["name"]
   'AnyVar'
   >>> response.json()["spec_metadata"]
   {'vrs_version': '2.0.1'}
