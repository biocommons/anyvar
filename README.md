# *AnyVar* - lightweight and portable variation storage and retrieval

AnyVar enables **registration**, **lookup**, and **search** of genetic variants across a distributed genomic resource network. Its goals are to:

* Provide an open source, off-the-shelf solution that lowers the technical barriers for genomic data resources to comprehensively describe and search genomic variants
* Support a broad range of query modes, including VRS ID lookups, HGVS expressions, gene-based searches, and genomic ranges
* Translate community nomenclatures and conventions into a universal model for variant representation
* Provide a community-driven, extensible platform for shared conventions and policy to realize the above goals

## Information

[![rtd](https://img.shields.io/badge/docs-readthedocs-green.svg)](http://anyvar.readthedocs.io/) [![changelog](https://img.shields.io/badge/docs-changelog-green.svg)](https://anyvar.readthedocs.io/en/latest/changelog.html) [![GitHub license](https://img.shields.io/github/license/biocommons/anyvar.svg)](https://github.com/biocommons/anyvar/blob/main/LICENSE)

## Latest Release

[![GitHub tag](https://img.shields.io/github/tag/biocommons/anyvar.svg)](https://github.com/biocommons/anyvar) [![pypi_rel](https://img.shields.io/pypi/v/anyvar.svg)](https://pypi.org/project/anyvar/)

## Development

[![action status](https://github.com/biocommons/anyvar/actions/workflows/python-package.yml/badge.svg)](https://github.com/biocommons/anyvar/actions/workflows/python-cqa.yml) [![issues](https://img.shields.io/github/issues-raw/biocommons/anyvar.svg)](https://github.com/biocommons/anyvar/issues)
[![GitHub Open Pull Requests](https://img.shields.io/github/issues-pr/biocommons/anyvar.svg)](https://github.com/biocommons/anyvar/pull/) [![GitHub Contributors](https://img.shields.io/github/contributors/biocommons/anyvar.svg)](https://github.com/biocommons/anyvar/graphs/contributors/) [![GitHub stars](https://img.shields.io/github/stars/biocommons/anyvar.svg?style=social&label=Stars)](https://github.com/biocommons/anyvar/stargazers) [![GitHub forks](https://img.shields.io/github/forks/biocommons/anyvar.svg?style=social&label=Forks)](https://github.com/biocommons/anyvar/forks)

## Installation

Currently, AnyVar can be installed from GitHub:

```
pip install git+https://github.com/biocommons/anyvar
```

See the [documentation](https://anyvar.readthedocs.io) for additional setup options and detailed instructions for initializing data dependencies.

## Examples

Use the Python API to directly instantiate and query a local AnyVar instance:

```pycon
>>> from anyvar.anyvar import AnyVar, create_storage, create_translator
>>> av = AnyVar(translator=create_translator(), object_store=create_storage())
>>> allele = Allele(**{"id": "ga4gh:VA.K7akyz9PHB0wg8wBNVlWAAdvMbJUJJfU", "digest": "K7akyz9PHB0wg8wBNVlWAAdvMbJUJJfU", "location": {"id": "ga4gh:SL.aCMcqLGKClwMWEDx3QWe4XSiGDlKXdB8", "digest": "aCMcqLGKClwMWEDx3QWe4XSiGDlKXdB8", "end": 87894077, "start": 87894076, "sequenceReference": {"refgetAccession": "SQ.ss8r_wB0-b9r44TQTMmVTI92884QvBiB"}}, "state": {"sequence": "T", "type": "LiteralSequenceExpression"}})
>>> av.put_object(allele)
'ga4gh:VA.K7akyz9PHB0wg8wBNVlWAAdvMbJUJJfU'
>>> av.get_object("ga4gh:VA.K7akyz9PHB0wg8wBNVlWAAdvMbJUJJfU")
Allele(id='ga4gh:VA.K7akyz9PHB0wg8wBNVlWAAdvMbJUJJfU', type='Allele', name=None, description=None, aliases=None, extensions=None, digest='K7akyz9PHB0wg8wBNVlWAAdvMbJUJJfU', expressions=None, location=SequenceLocation(id='ga4gh:SL.aCMcqLGKClwMWEDx3QWe4XSiGDlKXdB8', type='SequenceLocation', name=None, description=None, aliases=None, extensions=None, digest='aCMcqLGKClwMWEDx3QWe4XSiGDlKXdB8', sequenceReference=SequenceReference(id=None, type='SequenceReference', name=None, description=None, aliases=None, extensions=None, refgetAccession='SQ.ss8r_wB0-b9r44TQTMmVTI92884QvBiB', residueAlphabet=None, circular=None, sequence=None, moleculeType=None), start=87894076, end=87894077, sequence=None), state=LiteralSequenceExpression(id=None, type='LiteralSequenceExpression', name=None, description=None, aliases=None, extensions=None, sequence=sequenceString(root='T')))
```

Or issue a request against a live HTTP endpoint:

```pycon
>>> import requests
>>> response = requests.put("http://localhost:8000/variation", json={"definition": "NC_000010.11:g.87894077C>T"})
>>> response.json()
{'messages': [], 'object': {'id': 'ga4gh:VA.K7akyz9PHB0wg8wBNVlWAAdvMbJUJJfU', 'type': 'Allele', 'digest': 'K7akyz9PHB0wg8wBNVlWAAdvMbJUJJfU', 'location': {'id': 'ga4gh:SL.01EH5o6V6VEyNUq68gpeTwKE7xOo-WAy', 'type': 'SequenceLocation', 'digest': '01EH5o6V6VEyNUq68gpeTwKE7xOo-WAy', 'sequenceReference': {'type': 'SequenceReference', 'refgetAccession': 'SQ.ss8r_wB0-b9r44TQTMmVTI92884QvBiB'}, 'start': 87894076, 'end': 87894077}, 'state': {'type': 'LiteralSequenceExpression', 'sequence': 'T'}}, 'object_id': 'ga4gh:VA.K7akyz9PHB0wg8wBNVlWAAdvMbJUJJfU'}
>>> response = requests.get("http://localhost:8000/variation/ga4gh:VA.K7akyz9PHB0wg8wBNVlWAAdvMbJUJJfU")
>>> response.json()
{'messages': [], 'data': {'id': 'ga4gh:VA.K7akyz9PHB0wg8wBNVlWAAdvMbJUJJfU', 'type': 'Allele', 'digest': 'K7akyz9PHB0wg8wBNVlWAAdvMbJUJJfU', 'location': {'id': 'ga4gh:SL.aCMcqLGKClwMWEDx3QWe4XSiGDlKXdB8', 'type': 'SequenceLocation', 'digest': 'aCMcqLGKClwMWEDx3QWe4XSiGDlKXdB8', 'sequenceReference': {'type': 'SequenceReference', 'refgetAccession': 'SQ.ss8r_wB0-b9r44TQTMmVTI92884QvBiB'}, 'start': 87894076, 'end': 87894077}, 'state': {'type': 'LiteralSequenceExpression', 'sequence': 'T'}}}
```

## Feedback and contributing

We welcome [bug reports](https://github.com/biocommons/anyvar/issues/new?template=bug-report.md), [feature requests](https://github.com/biocommons/anyvar/issues/new?template=feature-request.md), and code contributions from users and interested collaborators. The [documentation](https://anyvar.readthedocs.io/en/latest/contributing.html) contains guidance for submitting feedback and contributing new code.
