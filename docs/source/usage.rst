Usage
!!!!!

.. note -- this is VERY sparse on purpose because we are still very much in alpha

First, to familiarize yourself with available endpoints, `SwaggerUI docs <https://swagger.io/tools/swagger-ui/>`_ are provided under the root path (``http://localhost:8000/`` in a local environment with default configurations).

.. code-block:: pycon

    >>> import requests
    >>> anyvar_hostname = "http://localhost:8000"
    >>> requests.get(anyvar_hostname).raise_for_status()
    # OK

Service Info
============

Use the ``/service-info`` endpoint to retrieve descriptive metadata about the AnyVar instance in a format compliant with the `GA4GH Service Info protocol <https://www.ga4gh.org/product/service-info/>`_.

.. code-block:: pycon

    >>> requests.get(f"{anyvar_hostname}/service-info").json()
    {'id': 'org.biocommons.anyvar', 'name': 'AnyVar', 'type': {'group': 'org.biocommons', 'artifact': 'anyvar', 'version': 'unknown'}, 'description': 'Register and retrieve GA4GH VRS variations and associated annotations.', 'organization': {'name': 'bioccommons', 'url': 'https://biocommons.org'}, 'contactUrl': 'mailto:alex.wagner@nationwidechildrens.org', 'documentationUrl': 'https://github.com/biocommons/anyvar', 'createdAt': '2025-06-01T00:00:00Z', 'updatedAt': '2025-06-01T00:00:00Z', 'environment': 'dev', 'version': 'unknown', 'spec_metadata': {'vrs_version': '2.0.1'}, 'impl_metadata': {'vrs_python_version': '2.1.2'}}

Variation Registration
======================

Submit a variation as a ``PUT`` request to ``/variation``. The variation is stored in AnyVar and returned as a VRS variation.

.. code-block:: pycon

    >>> payload = {
        "definition": "NC_000007.13:g.36561662_36561663del",
        "input_type": "Allele",
        "copies": 0,
        "copy_change": "complete genomic loss"
    }
    >>> response = requests.put(
        f"{anyvar_hostname}/variation",
        json=payload
    )
    >>> vrs_id = response.json()["object"]["id"]
    >>> vrs_id
    'ga4gh:VA.d6ru7RcuVO0-v3TtPFX5fZz-GLQDhMVb'

Variation Lookup
================

Issue a ``GET`` request to ``/variation/<VRS id>`` to retrieve a registered variant.

.. code-block:: pycon

    >>> response = requests.get(f"{anyvar_hostname}/variation/{vrs_id}")
    >>> response.json()
    {'messages': [], 'data': {'id': 'ga4gh:VA.d6ru7RcuVO0-v3TtPFX5fZz-GLQDhMVb', 'type': 'Allele', 'digest': 'd6ru7RcuVO0-v3TtPFX5fZz-GLQDhMVb', 'location': {'id': 'ga4gh:SL.JOFKL4nL5mRUlO_xLwQ8VOD1v7mxhs3I', 'type': 'SequenceLocation', 'digest': 'JOFKL4nL5mRUlO_xLwQ8VOD1v7mxhs3I', 'sequenceReference': {'type': 'SequenceReference', 'refgetAccession': 'SQ.IW78mgV5Cqf6M24hy52hPjyyo5tCCd86'}, 'start': 36561661, 'end': 36561663}, 'state': {'type': 'ReferenceLengthExpression', 'length': 0, 'sequence': '', 'repeatSubunitLength': 2}}}
