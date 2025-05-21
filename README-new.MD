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



<!--
	- Point `ANYVAR_STORAGE_URI` to an available database if you configured one in step 2. If you prefer to run AnyVar without a database backend (e.g., for lightweight testing), set this to `null`
	- Set `SEQREPO_DATAPROXY_URI` to local SeqRepo files or to a REST service instance

	Example:

	```shell
	export ANYVAR_STORAGE_URI=postgresql://anyvar:anyvar-pw@localhost:5432/anyvar
	export SEQREPO_DATAPROXY_URI=seqrepo+file:///usr/local/share/seqrepo/2024-12-20
	```
	See [Setting up Dependencies](#setting-up-dependencies) for detailed instructions regarding setting up environment variables -->

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

#### PostgreSQL (Optional)

AnyVar supports PostgreSQL databases. [Configure PostgreSQL for AnyVar.](docs/postgres.md)

#### Snowflake (Optional)

AnyVar can also utilize Snowflake. [Detailed instructions available.](docs/snowflake.md)


### Docker Compose

A complete environment can be set up using Docker Compose. [Full Docker Compose instructions.](docs/docker.md)

## Asynchronous Operations

AnyVar supports asynchronous VCF annotation for improved scalability. [See asynchronous operations README.](docs/async.md)

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

AnyVar uses Python's built-in logging. [Customize logging settings.](docs/logging-setup.md)

## Example Variation Data

For testing AnyVar with public datasets, [see example variation data.](docs/example-data.md)
