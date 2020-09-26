# AnyVar

*AnyVar* provides Python and REST interfaces to validate, normalize,
generate identifiers, and register biological sequence variation
according to the GA4GH Variation Representation standards.

## Supported Variation Types

* Alleles specified by HGVS, SPDI, beacon, or gnomad formats
* Unparsed text variation
* [future] Copy Number Variation
* [future] Genotypes (composed of Haplotypes)
* [future] Structural Variation/Translocations/Fusions

All types are assigned computed, digest-based identifiers based on the
underlying data. 


## Architecture

The *AnyVar* package is comprised of two components. The *AnyVar*
class is a façade over variation translation, validation, and storage
services.  It may be instantiated within any Python application. The
*AnyVar* REST interface exposes the *AnyVar* class functionality
through an OpenAPI-based REST interface.

The *AnyVar* class relies on external services for sequence data and
object storage, both specified as abstract interfaces.

* Sequences and sequence metadata "data proxy" (interface) provides
  data that are essential for translating identifiers and fetching
  sequence for normalization.  The two available data proxies are
  SeqRepoDataProxy and SeqRepoRESTDataProxy, for local a local SeqRepo
  instance and a remote
  [seqrepo-rest-service](https://github.com/biocommons/seqrepo-rest-service)
  instance.

* A storage interface for object storage.  *AnyVar* must instantiated
  with a storage object that satisfies a
  `collections.abc.MutableMapping` interface.  Three backends are
  common: 1) a `dict`, for emphemeral in-memory storage; 2)
  `anyvar.storage.shelf`, a dbm-based persistent storage mechanism
  that does not incur additional dependencies; 3)
  `anyvar.storage.redisobjectstore`, a Redis-backed storage interface
  that may be local or remote.

The *AnyVar* REST interface is implemented using the Connexion Python
library.  It may be deployed using any WSGI or ASGI framework.  The
default is currently to use the Flask development server, but this
will change as the product matures.


## Configuration

*AnyVar* should run without configuration.  The following environment
variables provide additional configuration:

* `GA4GH_VRS_DATAPROXY_URI` is a URI used to instantiate a
  `ga4gh.vrs.dataproxy` instance. See
  `ga4gh.vrs.dataproxy.create_dataproxy()` for permissible values.

* `ANYVAR_STORAGE_URI` configures storage used for AnyVar.  Examples
  are `memory:`, `file:///tmp/anyvar.dbm/` for shelf storage at
  `/tmp/anyvar.dbm`, or `redis:///15` for redis database 15 on
  localhost.

Example:

```
    $ export GA4GH_VR_DATAPROXY_URI=seqrepo+file:///usr/local/share/seqrepo/latest
    $ export ANYVAR_STORAGE_URI="redis:///15"
```



## Developer installation

    git clone https://github.com/biocommons/anyvar.git
    cd anyvar
    python3 -mvenv venv
    source venv/bin/activate
    pip install -U setuptools pip
    pip install -e '.[dev]'

Or, more simply:

    make devready
    source venv/bin/activate

Then, start the REST server with:

    python -m anyvar.restapi

In another terminal:

    curl http://localhost:5000/info


### Setting up Redis

A Redis-backed *AnyVar* installation may use any Redis instance, local
or remote.  The following instructions are for using a docker-based
Redis instance.

```
$ docker volume create anyvar_redis_vol
$ docker run --name anyvar_redis -v anyvar_redis_vol:/data -d redis redis-server --appendonly yes
$ python3 -m anyvar.restapi
```



## Deployment

1. Download
   [docker-compose.yml](https://raw.githubusercontent.com/biocommons/anyvar/master/docker-compose.yml).

2. Create a docker volume `seqrepo_vol` that contains a recent seqrepo release.

	a. If you already have seqrepo locally, do this to copy your local
    instance to a new volume:

		$ docker run --rm \
		  -v seqrepo_vol:/usr/local/share/seqrepo  \
		  -v /usr/local/share/seqrepo:/tmp/seqrepo \
		  alpine \
		  cp -av /tmp/seqrepo /usr/local/share/

	b. Otherwise, do this:

		$ docker run --rm \
		-v seqrepo_vol:/usr/local/share/seqrepo \
		biocommons/seqrepo:latest

Then, type:

    $ docker-compose up

Verify that *anyvar* is running like this:

	$ curl http://localhost:5000/info
    {
      "anyvar": {
        "version": "0.1.2.dev0+d20190508"
      },
      "ga4gh.vr": {
        "version": "0.2.0"
      }
    }

NOTE: The authoritative and sole source for version tags is the
repository. When a commit is tagged, that tag is automatically used as
the Python `__version__`, the docker image tag, and the version
reported at the `/info` endpoint.



