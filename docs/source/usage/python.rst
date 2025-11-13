Python API Usage
!!!!!!!!!!!!!!!!

Instantiating An AnyVar Instance
================================

The :py:class:`AnyVar <anyvar.anyvar.AnyVar>` class requires implementation of the :py:class:`Storage <anyvar.storage.base_storage.Storage>` and :py:class:`Translator <anyvar.translate.`

Basic Variant Operations
========================


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


Other
=====




* basic variation operations
* working with annotations
* working with mappings
* something about the translator?
* something about liftover?
