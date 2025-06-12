# AnyVar

_AnyVar_ provides Python and REST interfaces to validate, normalize, generate
identifiers, and register biological sequence variation according to the
[GA4GH Variation Representation Specification (VRS)](https://github.com/ga4gh/vrs).

## Information

[![license](https://img.shields.io/badge/license-Apache-green)](https://github.com/biocommons/anyvar/blob/main/LICENSE)

## Development

[![issues](https://img.shields.io/github/issues-raw/biocommons/anyvar.svg)](https://github.com/biocommons/anyvar/issues)
[![GitHub Open Pull Requests](https://img.shields.io/github/issues-pr/biocommons/anyvar.svg)](https://github.com/biocommons/anyvar/pull/) [![GitHub Contributors](https://img.shields.io/github/contributors/biocommons/anyvar.svg)](https://github.com/biocommons/anyvar/graphs/contributors/) [![GitHub stars](https://img.shields.io/github/stars/biocommons/anyvar.svg?style=social&label=Stars)](https://github.com/biocommons/anyvar/stargazers) [![GitHub forks](https://img.shields.io/github/forks/biocommons/anyvar.svg?style=social&label=Forks)](https://github.com/biocommons/anyvar/network)

## Known Issues

**You are encouraged to** [browse issues](https://github.com/biocommons/anyvar/issues). All known issues are listed there. Please report any issues you find.

## Quick Start

1. **Clone the AnyVar repository:**

	```shell
	git clone https://github.com/biocommons/anyvar
	cd anyvar
	```


2. **Set Environment Variables**

    Create a new file in the root directory of the repo called `.env`. In the next two steps, you will populate this file. You may want to see `.env.example` for reference.


2. If desired, create/start a database for AnyVar to use. See [Optional Dependencies - Databases](#optional-dependencies---databases) for detailed instructions on how to set up a database. Otherwise, set the `ANYVAR_STORAGE_URI` environment variable to `null` in your `.env` file to use AnyVar without a database.

3. **Configure required dependencies:**

	AnyVar has several required dependencies and a few optional ones. See [Setting up Dependencies](#setting-up-dependencies) for detailed instructions. Remember to set any environment variables in your `.env` file as directed.


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

### Optional Dependencies - Databases

AnyVar optionally supports several storage types. For general information about AnyVar's SQL storage options, see [the SQL Storage documentation](docss/sql.md). See below for more specific details on the various storage implementation options.


It is also possible to run AnyVar with no database. This is primarily useful for bulk annotations, such as annotating a VCF, where there is no real need to reuse previously computed VRS IDs. To run AnyVar with no database, set the `ANYVAR_STORAGE_URI` environment variable to `null` in your `.env` file.

#### PostgreSQL (Optional)

AnyVar supports PostgreSQL databases. [Configure PostgreSQL for AnyVar.](docs/postgres.md)

#### Snowflake (Optional)

AnyVar can also utilize Snowflake. [Detailed instructions available.](docs/snowflake.md)

## Asynchronous Operations

AnyVar supports asynchronous VCF annotation for improved scalability. [See asynchronous operations README.](docs/async.md)

## Developers

This section is intended for developers who contribute to AnyVar.

### Prerequisites

- Python >= 3.11
  - \_Note: Python 3.11 is required for developers contributing to AnyVar
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

1. Set up a database for testing. The default is a postgres database, which you can set up by following the instructions found here: `src/docs/postgres.md`.

2. Follow the [quickstart guide](#quick-start) to get AnyVar running

3. If you haven't run `make devready` before, open a new terminal and do so now. Then, source your venv by running: `source venv/3.11/bin/activate`

   Otherwise, you can skip straight to sourcing your venv: `source venv/3.11/bin/activate`

4. Within your venv, run `make testready` if you've never done so before. Otherwise, skip this step.

5. Ensure the following environment variables are set in your `.env` file:

   - `SEQREPO_DATAPROXY_URI` - See the quickstart guide above.
   - `ANYVAR_STORAGE_URI` - See the quickstart guide above.
   - `ANYVAR_TEST_STORAGE_URI` - This specifies the database to use for tests. If you set up a postgres database by following the README-pg guide suggested in step 1, then you can just copy/paste the example `ANYVAR_TEST_STORAGE_URI` found below.

   For example:

   ```shell
   ANYVAR_TEST_STORAGE_URI=postgresql://postgres:postgres@localhost/anyvar_test
   ANYVAR_STORAGE_URI=postgresql://anyvar:anyvar-pw@localhost:5432/anyvar
   SEQREPO_DATAPROXY_URI=seqrepo+file:///usr/local/share/seqrepo/latest
   ```

6. Finally, run tests with the following command:

   ```shell
   make test
   ```

### Notes

Currently, there is some interdependency between test modules -- namely, tests that rely
on reading data from storage assume that the data from `test_variation` has been
uploaded. A pytest hook ensures correct test order, but some test modules may not be
able to pass when run in isolation. By default, the tests will use a Postgres database
installation. To run the tests against a Snowflake database, change the
`ANYVAR_TEST_STORAGE_URI` to a Snowflake URI and run the tests.

For the `tests/test_vcf::test_vcf_registration_async` unit test to pass, a real broker and backend
are required for Celery to interact with. Set the `CELERY_BROKER_URL` and `CELERY_BACKEND_URL`
environment variables. The simplest solution is to run Redis locally and use that for both
the broker and the backend, eg:

```shell
% export CELERY_BROKER_URL="redis://"
% export CELERY_BACKEND_URL="redis://"
```

## Logging

AnyVar uses Python's built-in logging. To customize logging settings see [docs/logging.md](docs/logging.md)
