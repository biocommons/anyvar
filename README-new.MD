# AnyVar

*AnyVar* provides Python and REST interfaces to validate, normalize, generate identifiers, and register biological sequence variation according to the [GA4GH Variation Representation Specification (VRS)](https://github.com/ga4gh/vrs).

## Information

[![license](https://img.shields.io/badge/license-Apache-green)](https://github.com/biocommons/anyvar/blob/main/LICENSE)

## Development

[![issues](https://img.shields.io/github/issues-raw/biocommons/anyvar.svg)](https://github.com/biocommons/anyvar/issues)
[![GitHub Open Pull Requests](https://img.shields.io/github/issues-pr/biocommons/anyvar.svg)](https://github.com/biocommons/anyvar/pull/) [![GitHub Contributors](https://img.shields.io/github/contributors/biocommons/anyvar.svg)](https://github.com/biocommons/anyvar/graphs/contributors/) [![GitHub stars](https://img.shields.io/github/stars/biocommons/anyvar.svg?style=social\&label=Stars)](https://github.com/biocommons/anyvar/stargazers) [![GitHub forks](https://img.shields.io/github/forks/biocommons/anyvar.svg?style=social\&label=Forks)](https://github.com/biocommons/anyvar/network)

## Known Issues

**You are encouraged to** [browse issues](https://github.com/biocommons/anyvar/issues). All known issues are listed there. Please report any issues you find.

## Quick Start

Clone the AnyVar repository:

```shell
git clone https://github.com/biocommons/anyvar
cd anyvar
```

Configure required environment variables:

```shell
export ANYVAR_STORAGE_URI=postgresql://anyvar:anyvar-pw@localhost:5432/anyvar
export SEQREPO_DATAPROXY_URI=seqrepo+file:///usr/local/share/seqrepo/latest
```

Start the AnyVar server:

```shell
uvicorn anyvar.restapi.main:app --reload
```

Visit [`http://localhost:8000`](http://localhost:8000) to verify the REST API is running.

## Setting up Dependencies

AnyVar relies on the following components:

### SeqRepo

SeqRepo stores biological sequence data and can be accessed locally or via REST API. [Read how to set up SeqRepo locally or through Docker.](docs/seqrepo.md)

### UTA (Optional)

UTA is required only for interpreting non-genomic sequences (e.g., transcript accessions). [Instructions for setting up UTA locally or via Docker.](docs/uta.md)

### PostgreSQL

AnyVar supports PostgreSQL databases. [Configure PostgreSQL for AnyVar.](docs/postgres.md)

### Snowflake (Optional)

AnyVar can also utilize Snowflake. [Detailed instructions available.](docs/snowflake.md)

## Advanced Usage

### Visual Studio Code Dev Containers

AnyVar supports VS Code Dev Containers. [Read more here.](https://github.com/ga4gh/vrs-python/tree/main/notebooks/getting_started#dev-containers)

### GitHub Codespaces

AnyVar can be run easily using GitHub Codespaces for in-browser editing. [More details.](https://docs.github.com/en/codespaces/setting-your-user-preferences/setting-your-timeout-period-for-github-codespaces#about-the-idle-timeout)

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
