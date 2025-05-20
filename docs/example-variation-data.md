# AnyVar Example Variation Data

To effectively test and validate AnyVar’s capabilities, publicly available example variation datasets can be utilized. These datasets provide representative data to evaluate the normalization, registration, and retrieval functionalities.

## Available Public Datasets

The following public datasets are recommended for testing AnyVar:

### ClinVar SPDI

ClinVar SPDI datasets contain SPDI (Sequence Position Deletion Insertion) formatted variant data.

* **Dataset URL:** [ClinVar SPDI](https://storage.googleapis.com/clingen-public/gks-hackathon/variation_spdi/clinvar_2025_03_24.variation_spdi.000000000000.ndjson.gz)

#### Download and Prepare Dataset

```shell
curl -O https://storage.googleapis.com/clingen-public/gks-hackathon/variation_spdi/clinvar_2025_03_24.variation_spdi.000000000000.ndjson.gz

gzip -d clinvar_2025_03_24.variation_spdi.000000000000.ndjson.gz
```

Extract SPDI expressions:

```shell
jq -r '.spdi_source' clinvar_2025_03_24.variation_spdi.000000000000.ndjson > clinvar_spdi.txt
```

### ClinVar HGVS

ClinVar HGVS datasets provide Human Genome Variation Society (HGVS) nomenclature formatted variants.

* **Dataset URL:** [ClinVar HGVS](https://storage.googleapis.com/clingen-public/gks-hackathon/variation_hgvs/clinvar_2025_03_24.variation_hgvs.000000000000.ndjson.gz)

#### Download and Prepare Dataset

```shell
curl -O https://storage.googleapis.com/clingen-public/gks-hackathon/variation_hgvs/clinvar_2025_03_24.variation_hgvs.000000000000.ndjson.gz

gzip -d clinvar_2025_03_24.variation_hgvs.000000000000.ndjson.gz
```

Extract nucleotide expressions without issues:

```shell
jq -c '. | select(.issue == null)' clinvar_2025_03_24.variation_hgvs.000000000000.ndjson | jq -r '.expr[].nucleotide' > clinvar_hgvs_noissues.txt
```

### ClinVar VRS

ClinVar VRS datasets contain variations represented in Variation Representation Specification (VRS) format.

* **Dataset URL:** [ClinVar VRS](https://storage.googleapis.com/clingen-public/clinvar-gk-pilot/2025-03-23/dev/processed-vi.json.gz)

#### Download Dataset

```shell
curl -O https://storage.googleapis.com/clingen-public/clinvar-gk-pilot/2025-03-23/dev/processed-vi.json.gz

gzip -d processed-vi.json.gz
```

## Testing with Example Data

Use the prepared datasets to evaluate AnyVar’s capabilities:

* **Bulk Import:** Import datasets into AnyVar and validate normalization.
* **Performance Testing:** Measure the efficiency and scalability with large datasets.
* **Functional Validation:** Confirm accuracy in converting SPDI or HGVS expressions into VRS objects.

### Example Python Script for HGVS Testing

```python
import json

with open("clinvar_hgvs_noissues.txt") as file:
    hgvs_list = file.readlines()

# Replace with actual AnyVar normalization calls
for hgvs_expr in hgvs_list[:10]:  # testing first 10 for brevity
    print("Testing HGVS expression:", hgvs_expr.strip())
```

## Troubleshooting

* **Download Issues:** Ensure internet connectivity and correct URLs.
* **Data Extraction Errors:** Validate the presence of required tools (jq, gzip).
* **Import Issues:** Verify AnyVar environment configurations and dependencies are correctly set.

---

Your datasets are now prepared for extensive AnyVar testing. Refer to the primary AnyVar documentation for detailed usage instructions and integration guidelines.
