# anyvar

*anyvar* provides a REST interface to validate, normalize, identify,
and register biological sequence variation according to the GA4GH
Variation Representation standards:

* Alleles specified by HGVS, SPDI, beacon, or gnomad formats
* Unparsed text variation
* [future] Copy Number Variation
* [future] Genotypes (composed of Haplotypes)
* [future] Structural Variation/Translocations/Fusions

All types are assigned computed, digest-based identifiers based on the
underlying data. 


## Installation

The full functionality of *anyvar* requires external services:

* A local instance of SeqRepo and seqrepo-rest-service that provides
  sequences for normalization.
* A REDIS instance that provides persistent storage for variation.

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



## Developer installation

    git clone https://github.com/reece/anyvar.git
    cd anyvar
    python3 -mvenv venv
    source venv/bin/activate
    pip install -U setuptools pip
    pip install -e '.[dev]'

Or, more simply:

    make devready
    source venv/bin/activate

Then, start the server with:

    python -m anyvar

In another terminal:

    curl http://localhost:5000/info


## Other juicy notes

```
$ docker volume create anyvar_redis_vol
$ docker run --name anyvar_redis -v anyvar_redis_vol:/data -d redis redis-server --appendonly yes
$ python3 -m anyvar.restapi
```
