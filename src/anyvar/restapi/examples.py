"""Request and response examples for the REST API documentation.

Reuse payloads from REST API tests, variation fixtures, and usage documentation.
"""

from ga4gh.cat_vrs import models as cat_vrs
from ga4gh.vrs import models as vrs

from anyvar.core import metadata

_DELETION_GRCH37_ALLELE_DIGEST = "d6ru7RcuVO0-v3TtPFX5fZz-GLQDhMVb"
_DELETION_GRCH37_LOCATION_DIGEST = "JOFKL4nL5mRUlO_xLwQ8VOD1v7mxhs3I"
_DELETION_GRCH38_ALLELE_DIGEST = "QiKnpRR8S7SPoUE-RMUJJbT-RS1akuHA"
_DELETION_GRCH38_LOCATION_DIGEST = "0FYyfN4jIyShfruHwdYrSQ-2qmvuVNFK"
_BRAF_PROTEIN_ALLELE_DIGEST = "j4XnsLZcdzDIYa5pvvXM7t1wn9OITr0L"
_BRAF_PROTEIN_LOCATION_DIGEST = "t-3DrWALhgLdXHsupI-e-M00aL3HgK3y"
_MED12_ALLELE_DIGEST = "m-WuNP-2lw3copqMFAEAiiViDp7Re1Rc"
_MED12_LOCATION_DIGEST = "_9hCM5C6a-5s3MtaMeuJsu_uY17HIyf4"
_EGFR_PROTEIN_ALLELE_DIGEST = "sMA9h8fzDi0RvweMlxtD0_Oi8B-JZ1V-"
_EGFR_PROTEIN_LOCATION_DIGEST = "UOSDv-_5QNbKqgbCf--isFjvNZ5ZST09"
_NRAS_ALLELE_DIGEST = "EEk-kGY1YF1QgGShZ040hl3V5HWXsL4q"
_NRAS_LOCATION_DIGEST = "BP0NxO71lCOCWwwzfD_Ic19LIoGVG5J7"
_SUBSTITUTION_GRCH38_ALLELE_DIGEST = "K7akyz9PHB0wg8wBNVlWAAdvMbJUJJfU"
_SUBSTITUTION_GRCH38_LOCATION_DIGEST = "01EH5o6V6VEyNUq68gpeTwKE7xOo-WAy"

_GNOMAD_DEFINITION = "1-35227334-G-A"
_DELETION_STATE = {
    "type": "ReferenceLengthExpression",
    "length": 0,
    "sequence": "",
    "repeatSubunitLength": 2,
}

REFERENCE_ASSEMBLY_EXAMPLES = {
    "grch38": {
        "summary": "GRCh38 assembly",
        "description": "Use for a VCF with coordinates on GRCh38.",
        "value": "GRCh38",
    },
    "grch37": {
        "summary": "GRCh37 assembly",
        "description": "Use for a VCF with coordinates on GRCh37.",
        "value": "GRCh37",
    },
}

VARIATION_EXAMPLE_PAYLOAD = {
    "definition": "NC_000007.13:g.36561662_36561663del",
}

VARIATION_OPENAPI_EXAMPLES = {
    "hgvs_genomic": {
        "summary": "HGVS genomic substitution",
        "description": "Express a genomic substitution on the GRCh38 chromosome 10 reference sequence in HGVS notation.",
        "value": {"definition": "NC_000010.11:g.87894077C>T"},
    },
    "hgvs_deletion": {
        "summary": "HGVS genomic deletion",
        "description": "Express a genomic deletion on the GRCh37 chromosome 7 reference sequence in HGVS notation.",
        "value": VARIATION_EXAMPLE_PAYLOAD,
    },
    "hgvs_transcript": {
        "summary": "HGVS transcript substitution (BRAF V600E)",
        "description": "Express BRAF V600E on the NM_004333.6 transcript in HGVS notation.",
        "value": {"definition": "NM_004333.6:c.1799T>A"},
    },
    "hgvs_braf_genomic": {
        "summary": "HGVS genomic substitution (BRAF V600E)",
        "description": "Express BRAF V600E on the GRCh38 chromosome 7 reference sequence in HGVS notation.",
        "value": {"definition": "NC_000007.14:g.140753336A>T"},
    },
    "gnomad_grch37": {
        "summary": "gnomAD allele on GRCh37",
        "description": "Interpret the chromosome-position-reference-alternate expression on GRCh37.",
        "value": {
            "definition": _GNOMAD_DEFINITION,
            "assembly_name": "GRCh37",
        },
    },
    "gnomad_grch38": {
        "summary": "gnomAD allele on GRCh38",
        "description": "Interpret the chromosome-position-reference-alternate expression on GRCh38.",
        "value": {
            "definition": _GNOMAD_DEFINITION,
            "assembly_name": "GRCh38",
        },
    },
}

BULK_VARIATION_OPENAPI_EXAMPLES = {
    **{
        name: {**example, "value": [example["value"]]}
        for name, example in VARIATION_OPENAPI_EXAMPLES.items()
    },
    "mixed_formats": {
        "summary": "Multiple variations in different formats",
        "description": "Register HGVS genomic, HGVS transcript, and gnomAD expressions in one request.",
        "value": [
            VARIATION_OPENAPI_EXAMPLES["hgvs_genomic"]["value"],
            VARIATION_OPENAPI_EXAMPLES["hgvs_transcript"]["value"],
            VARIATION_OPENAPI_EXAMPLES["gnomad_grch37"]["value"],
        ],
    },
}

PUT_VRS_VARIATION_EXAMPLE_PAYLOAD = {
    "location": {
        "end": 87894077,
        "start": 87894076,
        "sequenceReference": {
            "refgetAccession": "SQ.ss8r_wB0-b9r44TQTMmVTI92884QvBiB",
            "type": "SequenceReference",
        },
        "type": "SequenceLocation",
    },
    "state": {"sequence": "T", "type": "LiteralSequenceExpression"},
    "type": "Allele",
}

VRS_VARIATION_OPENAPI_EXAMPLES = {
    "genomic_substitution": {
        "summary": "VRS genomic substitution",
        "description": "Register the GRCh38 chromosome 10 substitution as a VRS Allele object.",
        "value": PUT_VRS_VARIATION_EXAMPLE_PAYLOAD,
    },
    "deletion_grch37": {
        "summary": "VRS genomic deletion on GRCh37",
        "description": "Register the GRCh37 chromosome 7 deletion as a VRS Allele object.",
        "value": {
            "id": f"ga4gh:VA.{_DELETION_GRCH37_ALLELE_DIGEST}",
            "type": "Allele",
            "digest": _DELETION_GRCH37_ALLELE_DIGEST,
            "location": {
                "id": f"ga4gh:SL.{_DELETION_GRCH37_LOCATION_DIGEST}",
                "type": "SequenceLocation",
                "digest": _DELETION_GRCH37_LOCATION_DIGEST,
                "sequenceReference": {
                    "type": "SequenceReference",
                    "refgetAccession": "SQ.IW78mgV5Cqf6M24hy52hPjyyo5tCCd86",
                },
                "start": 36561661,
                "end": 36561663,
            },
            "state": _DELETION_STATE.copy(),
        },
    },
    "deletion_grch38": {
        "summary": "VRS genomic deletion on GRCh38",
        "description": "Register the GRCh38 chromosome 7 deletion as a VRS Allele object.",
        "value": {
            "id": f"ga4gh:VA.{_DELETION_GRCH38_ALLELE_DIGEST}",
            "digest": _DELETION_GRCH38_ALLELE_DIGEST,
            "type": "Allele",
            "location": {
                "id": f"ga4gh:SL.{_DELETION_GRCH38_LOCATION_DIGEST}",
                "digest": _DELETION_GRCH38_LOCATION_DIGEST,
                "type": "SequenceLocation",
                "sequenceReference": {
                    "refgetAccession": "SQ.F-LrLMe1SRpfUZHkQmvkVKFEGaoDeHul",
                    "type": "SequenceReference",
                },
                "start": 36522055,
                "end": 36522057,
            },
            "state": _DELETION_STATE.copy(),
        },
    },
}

VRS_OBJECT_ID_EXAMPLES = {
    "deletion_grch37": {
        "summary": "Genomic deletion on GRCh37",
        "description": f"First register the `{VARIATION_OPENAPI_EXAMPLES['hgvs_deletion']['summary']}` example using `PUT /variation`.",
        "value": VRS_VARIATION_OPENAPI_EXAMPLES["deletion_grch37"]["value"]["id"],
    },
    "deletion_grch38": {
        "summary": "Equivalent genomic deletion on GRCh38",
        "description": f"First register the `{VRS_VARIATION_OPENAPI_EXAMPLES['deletion_grch38']['summary']}` example using `PUT /vrs_variation`.",
        "value": VRS_VARIATION_OPENAPI_EXAMPLES["deletion_grch38"]["value"]["id"],
    },
    "braf_v600e": {
        "summary": "BRAF V600E on GRCh38",
        "description": f"First register the `{VARIATION_OPENAPI_EXAMPLES['hgvs_braf_genomic']['summary']}` example using `PUT /variation`.",
        "value": "ga4gh:VA.Otc5ovrw906Ack087o1fhegB4jDRqCAe",
    },
}

_SEARCH_REGIONS = {
    "deletion_grch37": {
        "summary": VRS_OBJECT_ID_EXAMPLES["deletion_grch37"]["summary"],
        "registration_example": VARIATION_OPENAPI_EXAMPLES["hgvs_deletion"],
        "location": VRS_VARIATION_OPENAPI_EXAMPLES["deletion_grch37"]["value"][
            "location"
        ],
    },
    "substitution_grch38": {
        "summary": "Genomic substitution on GRCh38",
        "registration_example": VARIATION_OPENAPI_EXAMPLES["hgvs_genomic"],
        "location": PUT_VRS_VARIATION_EXAMPLE_PAYLOAD["location"],
    },
}

SEARCH_ACCESSION_EXAMPLES = {
    name: {
        "summary": region["summary"],
        "description": (
            f"First register the `{region['registration_example']['summary']}` example using `PUT /variation`. "
            f"Select `{region['summary']}` for both start and end."
        ),
        "value": f"ga4gh:{region['location']['sequenceReference']['refgetAccession']}",
    }
    for name, region in _SEARCH_REGIONS.items()
}

SEARCH_START_EXAMPLES = {
    name: {
        "summary": region["summary"],
        "description": f"Select `{region['summary']}` for accession and end.",
        "value": region["location"]["start"],
    }
    for name, region in _SEARCH_REGIONS.items()
}

SEARCH_END_EXAMPLES = {
    name: {
        "summary": region["summary"],
        "description": f"Select `{region['summary']}` for accession and start.",
        "value": region["location"]["end"],
    }
    for name, region in _SEARCH_REGIONS.items()
}

EXTENSION_OPENAPI_EXAMPLES = {
    "source_dataset": {
        "summary": "Source dataset",
        "description": "Attach the source dataset name to the selected registered object.",
        "value": {"name": "source_dataset", "value": "gnomAD_v4.1"},
    },
    "somatic_classification": {
        "summary": "Somatic classification (BRAF V600E)",
        "description": f"First register the `{VARIATION_OPENAPI_EXAMPLES['hgvs_braf_genomic']['summary']}` example using `PUT /variation`. Select `{VRS_OBJECT_ID_EXAMPLES['braf_v600e']['summary']}` as the object ID.",
        "value": {
            "name": "clinvar_somatic_classification",
            "value": "Oncogenic",
        },
    },
}

EXTENSION_NAME_EXAMPLES = {
    "source_dataset": {
        "summary": EXTENSION_OPENAPI_EXAMPLES["source_dataset"]["summary"],
        "description": f"First add the `{EXTENSION_OPENAPI_EXAMPLES['source_dataset']['summary']}` example using `POST /object/{{vrs_id}}/extensions`. Use the same object ID for this request.",
        "value": EXTENSION_OPENAPI_EXAMPLES["source_dataset"]["value"]["name"],
    },
    "somatic_classification": {
        "summary": "Somatic classification",
        "description": f"First add the `{EXTENSION_OPENAPI_EXAMPLES['somatic_classification']['summary']}` example using `POST /object/{{vrs_id}}/extensions`. Select `{VRS_OBJECT_ID_EXAMPLES['braf_v600e']['summary']}` as the object ID.",
        "value": EXTENSION_OPENAPI_EXAMPLES["somatic_classification"]["value"]["name"],
    },
}

MAPPING_OPENAPI_EXAMPLES = {
    "liftover": {
        "summary": "Map a GRCh37 deletion to GRCh38",
        "description": f"First register the `{VRS_VARIATION_OPENAPI_EXAMPLES['deletion_grch37']['summary']}` and `{VRS_VARIATION_OPENAPI_EXAMPLES['deletion_grch38']['summary']}` examples using `PUT /vrs_variation`. Select `{VRS_OBJECT_ID_EXAMPLES['deletion_grch37']['summary']}` as the source object ID.",
        "value": {
            "dest_id": VRS_OBJECT_ID_EXAMPLES["deletion_grch38"]["value"],
            "mapping_type": metadata.VariationMappingType.LIFTOVER_TO.value,
        },
    },
}

PROTEIN_SEQUENCE_CONSEQUENCE_EXAMPLE = cat_vrs.CategoricalVariant(
    id="civic.mpid:12",
    name="BRAF V600E",
    constraints=[
        cat_vrs.Constraint(
            root=cat_vrs.DefiningAlleleConstraint(
                allele=vrs.Allele(
                    id=f"ga4gh:VA.{_BRAF_PROTEIN_ALLELE_DIGEST}",
                    digest=_BRAF_PROTEIN_ALLELE_DIGEST,
                    location=vrs.SequenceLocation(
                        id=f"ga4gh:SL.{_BRAF_PROTEIN_LOCATION_DIGEST}",
                        digest=_BRAF_PROTEIN_LOCATION_DIGEST,
                        sequenceReference=vrs.SequenceReference(
                            refgetAccession="SQ.cQvw4UsHHRRlogxbWCB8W-mKD4AraM9y",
                            moleculeType=vrs.MoleculeType.PROTEIN,
                        ),
                        start=599,
                        end=600,
                    ),
                    state=vrs.LiteralSequenceExpression(
                        sequence=vrs.sequenceString("E"),
                    ),
                )
            )
        )
    ],
)

CANONICAL_ALLELE_EXAMPLE = cat_vrs.CategoricalVariant(
    id="clingen.allele:CA413542193",
    name="NM_005120.3(MED12):c.6352C>T (p.Gln2118Ter)",
    constraints=[
        cat_vrs.Constraint(
            root=cat_vrs.DefiningAlleleConstraint(
                allele=vrs.Allele(
                    id=f"ga4gh:VA.{_MED12_ALLELE_DIGEST}",
                    digest=_MED12_ALLELE_DIGEST,
                    location=vrs.SequenceLocation(
                        id=f"ga4gh:SL.{_MED12_LOCATION_DIGEST}",
                        digest=_MED12_LOCATION_DIGEST,
                        end=71141314,
                        start=71141313,
                        sequenceReference=vrs.SequenceReference(
                            refgetAccession="SQ.w0WZEvgJF0zf_P4yyTzjjv9oW1z61HHP",
                            moleculeType=vrs.MoleculeType.GENOMIC,
                        ),
                    ),
                    state=vrs.LiteralSequenceExpression(
                        sequence=vrs.sequenceString("T")
                    ),
                )
            )
        )
    ],
)

EGFR_PROTEIN_SEQUENCE_CONSEQUENCE_EXAMPLE = cat_vrs.CategoricalVariant.model_validate(
    {
        "id": "civic.mpid:34",
        "name": "EGFR T790M",
        "constraints": [
            {
                "type": "DefiningAlleleConstraint",
                "allele": {
                    "id": f"ga4gh:VA.{_EGFR_PROTEIN_ALLELE_DIGEST}",
                    "type": "Allele",
                    "digest": _EGFR_PROTEIN_ALLELE_DIGEST,
                    "location": {
                        "id": f"ga4gh:SL.{_EGFR_PROTEIN_LOCATION_DIGEST}",
                        "type": "SequenceLocation",
                        "digest": _EGFR_PROTEIN_LOCATION_DIGEST,
                        "sequenceReference": {
                            "type": "SequenceReference",
                            "refgetAccession": "SQ.vyo55F6mA6n2LgN4cagcdRzOuh38V4mE",
                        },
                        "start": 789,
                        "end": 790,
                    },
                    "state": {
                        "type": "LiteralSequenceExpression",
                        "sequence": "M",
                    },
                },
            },
        ],
    },
)

NRAS_CANONICAL_ALLELE_EXAMPLE = cat_vrs.CategoricalVariant.model_validate(
    {
        "id": "clingen.allele:CA321211",
        "name": "NC_000011.10:g.68032291C>T",
        "constraints": [
            {
                "type": "DefiningAlleleConstraint",
                "allele": {
                    "id": f"ga4gh:VA.{_NRAS_ALLELE_DIGEST}",
                    "type": "Allele",
                    "digest": _NRAS_ALLELE_DIGEST,
                    "location": {
                        "id": f"ga4gh:SL.{_NRAS_LOCATION_DIGEST}",
                        "type": "SequenceLocation",
                        "digest": _NRAS_LOCATION_DIGEST,
                        "sequenceReference": {
                            "type": "SequenceReference",
                            "refgetAccession": "SQ.2NkFm8HK88MqeNkCgj78KidCAXgnsfV1",
                        },
                        "start": 68032290,
                        "end": 68032291,
                    },
                    "state": {
                        "type": "LiteralSequenceExpression",
                        "sequence": "T",
                    },
                },
            },
        ],
    },
)

PROTEIN_SEQUENCE_CONSEQUENCE_OPENAPI_EXAMPLES = {
    "braf_v600e": {
        "summary": PROTEIN_SEQUENCE_CONSEQUENCE_EXAMPLE.name,
        "description": "Register a categorical variant defined by the BRAF V600E protein allele.",
        "value": PROTEIN_SEQUENCE_CONSEQUENCE_EXAMPLE.model_dump(
            mode="json", exclude_none=True
        ),
    },
    "egfr_t790m": {
        "summary": EGFR_PROTEIN_SEQUENCE_CONSEQUENCE_EXAMPLE.name,
        "description": "Register a categorical variant defined by the EGFR T790M protein allele.",
        "value": EGFR_PROTEIN_SEQUENCE_CONSEQUENCE_EXAMPLE.model_dump(
            mode="json", exclude_none=True
        ),
    },
}

PROTEIN_SEQUENCE_CONSEQUENCE_ID_EXAMPLES = {
    "braf_v600e": {
        "summary": PROTEIN_SEQUENCE_CONSEQUENCE_OPENAPI_EXAMPLES["braf_v600e"][
            "summary"
        ],
        "description": f"First register the `{PROTEIN_SEQUENCE_CONSEQUENCE_OPENAPI_EXAMPLES['braf_v600e']['summary']}` example using `PUT /categorical_variants/protein_sequence_consequences`.",
        "value": PROTEIN_SEQUENCE_CONSEQUENCE_EXAMPLE.id,
    },
    "egfr_t790m": {
        "summary": PROTEIN_SEQUENCE_CONSEQUENCE_OPENAPI_EXAMPLES["egfr_t790m"][
            "summary"
        ],
        "description": f"First register the `{PROTEIN_SEQUENCE_CONSEQUENCE_OPENAPI_EXAMPLES['egfr_t790m']['summary']}` example using `PUT /categorical_variants/protein_sequence_consequences`.",
        "value": EGFR_PROTEIN_SEQUENCE_CONSEQUENCE_EXAMPLE.id,
    },
}

CANONICAL_ALLELE_OPENAPI_EXAMPLES = {
    "med12": {
        "summary": "MED12 Gln2118Ter",
        "description": "Register a categorical variant defined by the MED12 Gln2118Ter genomic allele.",
        "value": CANONICAL_ALLELE_EXAMPLE.model_dump(mode="json", exclude_none=True),
    },
    "nras": {
        "summary": "NRAS Pro22Ser",
        "description": "Register a categorical variant defined by the NRAS Pro22Ser genomic allele.",
        "value": NRAS_CANONICAL_ALLELE_EXAMPLE.model_dump(
            mode="json", exclude_none=True
        ),
    },
}

CANONICAL_ALLELE_ID_EXAMPLES = {
    "med12": {
        "summary": CANONICAL_ALLELE_OPENAPI_EXAMPLES["med12"]["summary"],
        "description": f"First register the `{CANONICAL_ALLELE_OPENAPI_EXAMPLES['med12']['summary']}` example using `PUT /categorical_variants/canonical_alleles`.",
        "value": CANONICAL_ALLELE_EXAMPLE.id,
    },
    "nras": {
        "summary": CANONICAL_ALLELE_OPENAPI_EXAMPLES["nras"]["summary"],
        "description": f"First register the `{CANONICAL_ALLELE_OPENAPI_EXAMPLES['nras']['summary']}` example using `PUT /categorical_variants/canonical_alleles`.",
        "value": NRAS_CANONICAL_ALLELE_EXAMPLE.id,
    },
}

CATEGORICAL_VARIANT_MEMBER_EXAMPLES = {
    "braf_v600e": {
        "summary": f"{PROTEIN_SEQUENCE_CONSEQUENCE_OPENAPI_EXAMPLES['braf_v600e']['summary']} protein allele",
        "description": f"First register the `{PROTEIN_SEQUENCE_CONSEQUENCE_OPENAPI_EXAMPLES['braf_v600e']['summary']}` example using `PUT /categorical_variants/protein_sequence_consequences`.",
        "value": PROTEIN_SEQUENCE_CONSEQUENCE_EXAMPLE.constraints[0].root.allele.id,  # type: ignore
    },
    "egfr_t790m": {
        "summary": f"{PROTEIN_SEQUENCE_CONSEQUENCE_OPENAPI_EXAMPLES['egfr_t790m']['summary']} protein allele",
        "description": f"First register the `{PROTEIN_SEQUENCE_CONSEQUENCE_OPENAPI_EXAMPLES['egfr_t790m']['summary']}` example using `PUT /categorical_variants/protein_sequence_consequences`.",
        "value": EGFR_PROTEIN_SEQUENCE_CONSEQUENCE_EXAMPLE.constraints[  # type: ignore
            0
        ].root.allele.id,  # type: ignore
    },
}

REGISTER_VARIATION_RESPONSE_EXAMPLES = [
    {
        "input_variation": {
            "definition": VARIATION_EXAMPLE_PAYLOAD["definition"],
            "input_type": "Allele",
            "copies": 0,
            "copy_change": "complete genomic loss",
            "assembly_name": None,
        },
        "messages": [],
        "object": VRS_VARIATION_OPENAPI_EXAMPLES["deletion_grch37"]["value"],
        "object_id": VRS_OBJECT_ID_EXAMPLES["deletion_grch37"]["value"],
    },
]

GET_OBJECT_RESPONSE_EXAMPLES = [
    {
        "messages": [],
        "data": {
            **PUT_VRS_VARIATION_EXAMPLE_PAYLOAD,
            "digest": _SUBSTITUTION_GRCH38_ALLELE_DIGEST,
            "id": f"ga4gh:VA.{_SUBSTITUTION_GRCH38_ALLELE_DIGEST}",
            "location": {
                **PUT_VRS_VARIATION_EXAMPLE_PAYLOAD["location"],
                "digest": _SUBSTITUTION_GRCH38_LOCATION_DIGEST,
                "id": f"ga4gh:SL.{_SUBSTITUTION_GRCH38_LOCATION_DIGEST}",
            },
        },
    },
]
