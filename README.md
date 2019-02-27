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



# Developer installation

```
# Clone the repo. Then:

cd anyvar
python3.7 -mvenv venv/3.7
source venv/3.7/bin/activate
pip install -U setuptools pip
pip install -e '.[dev]'
python -m anyvar

# then open http://localhost:5000/v0/ui/
```


See https://docs.google.com/spreadsheets/d/1_oi_BBRE71PE8FpVqTwKnh5uibsTG2pp2ZaHxsekotg/edit
