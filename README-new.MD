# AnyVar

_AnyVar_ provides Python and REST interfaces to validate, normalize, generate identifiers, and register biological sequence variation according to the [GA4GH Variation Representation Specification (VRS)](https://github.com/ga4gh/vrs).

## Information

[![license](https://img.shields.io/badge/license-Apache-green)](https://github.com/biocommons/anyvar/blob/main/LICENSE)

## Development

[![issues](https://img.shields.io/github/issues-raw/biocommons/anyvar.svg)](https://github.com/biocommons/anyvar/issues)
[![GitHub Open Pull Requests](https://img.shields.io/github/issues-pr/biocommons/anyvar.svg)](https://github.com/biocommons/anyvar/pull/) [![GitHub Contributors](https://img.shields.io/github/contributors/biocommons/anyvar.svg)](https://github.com/biocommons/anyvar/graphs/contributors/) [![GitHub stars](https://img.shields.io/github/stars/biocommons/anyvar.svg?style=social&label=Stars)](https://github.com/biocommons/anyvar/stargazers) [![GitHub forks](https://img.shields.io/github/forks/biocommons/anyvar.svg?style=social&label=Forks)](https://github.com/biocommons/anyvar/network)

## Known Issues

**You are encouraged to** [browse issues](https://github.com/biocommons/anyvar/issues). All known issues are listed there. Please report any issues you find.

## Quick Start

1. Clone the AnyVar repository:

	```shell
	git clone https://github.com/biocommons/anyvar
	cd anyvar
	```
2. If desired, create/start a database for AnyVar to use. See [Setting up Dependencies](#setting-up-dependencies) for detailed instructions on how to set up a database

3. **Configure required dependencies:**

	AnyVar has several required dependencies and a few optional ones. See [Setting up Dependencies](#setting-up-dependencies) for detailed instructions.


4. **Start the AnyVar server:**

	```shell
	uvicorn anyvar.restapi.main:app --reload
	```

5. Visit [`http://localhost:8000`](http://localhost:8000) to verify the REST API is running.

## Setting up Dependencies

### Required Dependencies

#### SeqRepo

SeqRepo stores biological sequence data and can be accessed locally or via REST API. [Read how to set up SeqRepo locally or through Docker.](docs/seqrepo.md)

#### UTA

UTA (Universal Transcript Archive) stores transcripts aligned to sequence references. [Read how to set up UTA locally or via Docker.](docs/uta.md)

### Optional Dependencies

AnyVar optionally supports several storage types. For general information about AnyVar's SQL storage options, see [the SQL Storage documentation](docss/sql.md). See below for more specific details on the various storage implementation options.

#### PostgreSQL (Optional)

AnyVar supports PostgreSQL databases. [Configure PostgreSQL for AnyVar.](docs/postgres.md)

#### Snowflake (Optional)

AnyVar can also utilize Snowflake. [Detailed instructions available.](docs/snowflake.md)

## Asynchronous Operations

AnyVar supports asynchronous VCF annotation for improved scalability. [See asynchronous operations README.](docs/async.md)

## Developers

This section is intended for developers who contribute to AnyVar.

### Prerequisites

- Python >= 3.9
  - _Note: Python 3.11 is required for developers contributing to AnyVar_
- [Docker](https://docs.docker.com/engine/install/)

### Installing for development

```shell
git clone https://github.com/biocommons/anyvar.git
cd anyvar
make devready
source venv/3.11/bin/activate
pre-commit install
```

## Testing

Run tests:

```shell
make test
```

Specify test database with:

```shell
export ANYVAR_TEST_STORAGE_URI=postgresql://postgres:postgres@localhost/anyvar_test
```

## Logging

AnyVar uses Python's built-in logging. To customize logging settings see [docs/logging.md](docs/logging.md)
