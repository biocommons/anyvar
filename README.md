# anyvar

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


# Developer installation

    git clone https://github.com/reece/anyvar.git
    cd anyvar
    python3 -mvenv venv
    source venv/bin/activate
    pip install -U setuptools pip
    pip install -e '.[dev]'
    python -m anyvar

In another terminal:

    curl http://localhost:5000/info


# Docker images

**IMPORTANT:** The docker images are brand new. They should be the
easiest way to kick tires.

Download `docker-compose.yml` from the repo.  Then, type:

	docker-compose up

Warning: This will download approximately 10GB of sequence data to use
for normalization and accession matching.

In another terminal:

    curl http://localhost:5000/info
