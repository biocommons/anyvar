# variation-sandbox
Sandbox to implement various proof-of-concept variation REST services

# Components
## ClinGen Allele Registry wrapper
**wrap the CAR REST API to return VMC structures rather than CAR
alleles**
* `/car/ca/:id` (GET)
* `/car/ca?hgvs=` (GET)

## Variation Registry
**single registry of variation of diverse definition
  types, returning a deterministic computed identifier**
  
Supported variation definition types are/will be: HGVS alleles, HGVS
haplotypes, HGVS genotypes, VCF alleles, CAR allele sets, dbSNP allele
sets, human text.

* `/vr/variation/` (POST)
* `/vr/variation/:id` (GET)


# Caveats
This is a sandbox. The code and code structure are a messy.  I'm
intentionally not worrying about code organization right now.

Specific grievances (from the author):
1. There's a lot of functionality that would be better split into
separate repos.
2. The REST API and Python API code for each service are comingled.
3. The API is unversioned.



# Developer installation

```
# Clone the repo. Then:

cd variation-sandbox
python3.6 -mvenv venv/3.6
source venv/3.6/bin/activate
pip install -U setuptools pip
pip install -e '.[dev]'
python -m variationsandbox.restapi

# then open http://0.0.0.0:9090/v0/ui/
```
