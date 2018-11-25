# variation-sandbox
Sandbox to implement various proof-of-concept variation services

# Plans
* **ClinGen Allele Registry wrapper** — wraps the CAR REST API to
  return VMC structures rather than CAR alleles.
* **Variation Registry** — registers a variety of variation definition
  types and returns a deterministic computed identifier.  Supported
  variation definition types are/will be: HGVS alleles, HGVS
  haplotypes, HGVS genotypes, VCF alleles, CAR allele sets, dbSNP
  allele sets, human text.


# Developer installation

1. Clone the repo
1. cd variation-sandbox
1. python3.6 -mvenv venv/3.6
1. source venv/bin/activate
1. pip install -U setuptools pip
1. pip install -e '.[dev]'
1. python -m variationsandbox.restapi



