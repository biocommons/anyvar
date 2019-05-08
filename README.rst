anyvar
!!!!!!

**WORK IN PROGRESS • descriptions are mostly aspirational**

Python library and REST interface to validation, normalize, project,
identify, and register variation of these types:

* Alleles specified by HGVS, SPDI, beacon, or gnomad formats
* Haplotypes (composed of Alleles)
* Genotypes (composed of Haplotypes)
* Copy Number Variation
* Translocations
* Unparsed text variation

All types are assigned computed identifiers based on a digest.

See https://docs.google.com/spreadsheets/d/1_oi_BBRE71PE8FpVqTwKnh5uibsTG2pp2ZaHxsekotg/edit


Developer installation
!!!!!!!!!!!!!!!!!!!!!!

::

   git clone https://github.com/reece/anyvar.git
   cd anyvar
   python3 -mvenv venv
   source venv/bin/activate
   pip install -U setuptools pip
   pip install -e '.[dev]'
   python -m anyvar

In another terminal::

  curl http://localhost:5000/info


Docker images
!!!!!!!!!!!!!

.. note:: The authoritative source for version tags is the
	  repository. When commit is tagged, that tag is automatically
	  used as the Python `__version__`, the docker image tag, and
	  the version reported at the `/info` endpoint.


Without local data (limited functionality)
@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@

Basic functionality may be tested directly from the docker image::

   docker run --rm -dit -p 5000:5000 reece/anyvar


With local data (in containers)
@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@

Download `docker-compose.yml` from the repo.  Then, type::

  docker-compose up

Warning: This will download approximately 10GB of sequence data to use
for normalization and accession matching.

Either way, check for a heartbeat
@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@

::

   curl http://localhost:5000/info

should show something like::

  {
    "anyvar": {
      "version": "0.1.2.dev0+d20190508"
    },
    "ga4gh.vr": {
      "version": "0.2.0"
    }
  }
