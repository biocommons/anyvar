"""Test REST projection of genomic SPDI expressions to transcript and protein."""

from http import HTTPStatus

import pytest

from anyvar.core import metadata

PROJECTION_CASES = [
    {
        "label": "snp",
        "variation_id": "2068486",
        "spdi": "NC_000001.11:62513551:T:A",
        "clinvar_cdna": "NM_001367561.1:c.4174A>T",
        "clinvar_protein": "NP_001354490.1:p.Met1392Leu",
        "messages": [],
        "genomic": {
            "id": "ga4gh:VA.XKjKAlr0tojSt610fYjibQpMjaXWA2lv",
            "type": "Allele",
            "digest": "XKjKAlr0tojSt610fYjibQpMjaXWA2lv",
            "location": {
                "id": "ga4gh:SL.-17kuFPN45vt68MSTL0swmsIq1AjK8qJ",
                "type": "SequenceLocation",
                "digest": "-17kuFPN45vt68MSTL0swmsIq1AjK8qJ",
                "sequenceReference": {
                    "type": "SequenceReference",
                    "refgetAccession": "SQ.Ya6Rs7DHhDeg7YaOSg1EoNi3U_nQ9SvO",
                },
                "start": 62513551,
                "end": 62513552,
            },
            "state": {"type": "LiteralSequenceExpression", "sequence": "A"},
        },
        "transcript": {
            "id": "ga4gh:VA.qFzKDWrAh-CDHyOpQu2k1YuXfGng8q3k",
            "type": "Allele",
            "digest": "qFzKDWrAh-CDHyOpQu2k1YuXfGng8q3k",
            "location": {
                "id": "ga4gh:SL.z_Qf_Ihm8JNCmzcvd-mKTyRMzn7tx-Pf",
                "type": "SequenceLocation",
                "digest": "z_Qf_Ihm8JNCmzcvd-mKTyRMzn7tx-Pf",
                "sequenceReference": {
                    "type": "SequenceReference",
                    "refgetAccession": "SQ.RNFGe-eUOd_q881jYK-brz9fYVzjFg_d",
                },
                "start": 4295,
                "end": 4296,
            },
            "state": {"type": "LiteralSequenceExpression", "sequence": "T"},
        },
        "protein": {
            "id": "ga4gh:VA.Ak5dd7_Rwi_Xc0qJw5CC5rk-OBsPZnsb",
            "type": "Allele",
            "digest": "Ak5dd7_Rwi_Xc0qJw5CC5rk-OBsPZnsb",
            "location": {
                "id": "ga4gh:SL.QRYu_fqKBiz3Y-7bbOOszev68ICDn1n2",
                "type": "SequenceLocation",
                "digest": "QRYu_fqKBiz3Y-7bbOOszev68ICDn1n2",
                "sequenceReference": {
                    "type": "SequenceReference",
                    "refgetAccession": "SQ.0K1sWVoYzfuWsUt0T8-BOXgmmsOVzZ_A",
                },
                "start": 1391,
                "end": 1392,
            },
            "state": {"type": "LiteralSequenceExpression", "sequence": "L"},
        },
    },
    {
        "label": "insertion",
        "variation_id": "933660",
        "spdi": "NC_000001.11:94014685::T",
        "clinvar_cdna": "NM_001425324.1:c.5095_5096insA",
        "clinvar_protein": "NP_001412253.1:p.Ala1699Aspfs",
        "messages": [
            "Projection skipped: could not derive alternate protein state for "
            "NP_000341.2"
        ],
        "genomic": {
            "id": "ga4gh:VA.pePyWtQvzIyNEMJhzwZz4cnRtLTT_Xr-",
            "type": "Allele",
            "digest": "pePyWtQvzIyNEMJhzwZz4cnRtLTT_Xr-",
            "location": {
                "id": "ga4gh:SL.sYfpAWz1rVe1RB2oGLMehjDC2oqrIWBC",
                "type": "SequenceLocation",
                "digest": "sYfpAWz1rVe1RB2oGLMehjDC2oqrIWBC",
                "sequenceReference": {
                    "type": "SequenceReference",
                    "refgetAccession": "SQ.Ya6Rs7DHhDeg7YaOSg1EoNi3U_nQ9SvO",
                },
                "start": 94014685,
                "end": 94014685,
            },
            "state": {"type": "LiteralSequenceExpression", "sequence": "T"},
        },
        "transcript": {
            "id": "ga4gh:VA.hj68d4XmQVOYyuj-dD5npjCk7LPF46gC",
            "type": "Allele",
            "digest": "hj68d4XmQVOYyuj-dD5npjCk7LPF46gC",
            "location": {
                "id": "ga4gh:SL.g9ummqlWoSCdUWomhGqqVyLqvk7-9Xp2",
                "type": "SequenceLocation",
                "digest": "g9ummqlWoSCdUWomhGqqVyLqvk7-9Xp2",
                "sequenceReference": {
                    "type": "SequenceReference",
                    "refgetAccession": "SQ.vNQGF2g2py-LVs0TWiB2rqXioyDC4Ww3",
                },
                "start": 5420,
                "end": 5420,
            },
            "state": {"type": "LiteralSequenceExpression", "sequence": "A"},
        },
        "protein": None,
    },
    {
        "label": "deletion",
        "variation_id": "2633555",
        "spdi": "NC_000001.11:150509934:CTCTC:CTC",
        "clinvar_cdna": "NM_022664.3:c.240_241del",
        "clinvar_protein": "NP_073155.2:p.Gln81fs",
        "messages": [
            "Projection skipped: could not derive alternate protein state for "
            "NP_004416.2"
        ],
        "genomic": {
            "id": "ga4gh:VA.mkLU2yL862kqFSvsTsB_JhSg8Cvg88BG",
            "type": "Allele",
            "digest": "mkLU2yL862kqFSvsTsB_JhSg8Cvg88BG",
            "location": {
                "id": "ga4gh:SL.lATPyMuwVuHvSnMktrj-NfJ3CkC6u5I3",
                "type": "SequenceLocation",
                "digest": "lATPyMuwVuHvSnMktrj-NfJ3CkC6u5I3",
                "sequenceReference": {
                    "type": "SequenceReference",
                    "refgetAccession": "SQ.Ya6Rs7DHhDeg7YaOSg1EoNi3U_nQ9SvO",
                },
                "start": 150509934,
                "end": 150509939,
            },
            "state": {
                "type": "ReferenceLengthExpression",
                "length": 3,
                "sequence": "CTC",
                "repeatSubunitLength": 2,
            },
        },
        "transcript": {
            "id": "ga4gh:VA.OFy3vDHLxHgxFCVRXt2e8j8C_yFVrnpX",
            "type": "Allele",
            "digest": "OFy3vDHLxHgxFCVRXt2e8j8C_yFVrnpX",
            "location": {
                "id": "ga4gh:SL.B-EDJvWA8CAbJFu2GDgbpmjX0hh0JCQp",
                "type": "SequenceLocation",
                "digest": "B-EDJvWA8CAbJFu2GDgbpmjX0hh0JCQp",
                "sequenceReference": {
                    "type": "SequenceReference",
                    "refgetAccession": "SQ.eGUZSUd48UdQAzYgnsEW9ljTfx45zdpk",
                },
                "start": 337,
                "end": 342,
            },
            "state": {
                "type": "ReferenceLengthExpression",
                "length": 3,
                "sequence": "CTC",
                "repeatSubunitLength": 2,
            },
        },
        "protein": None,
    },
]

NO_MANE_PROJECTION_CASES = [
    {
        "label": "intronic_plus",
        "variation_id": "707618",
        "clinvar_name": "NM_198576.4(AGRN):c.3516+7C>T",
        "spdi": "NC_000001.11:1047460:C:T",
        "genomic": {
            "id": "ga4gh:VA.Qs90vys_MRPyU62F7EdL2oVWZWn8KCi7",
            "type": "Allele",
            "digest": "Qs90vys_MRPyU62F7EdL2oVWZWn8KCi7",
            "location": {
                "id": "ga4gh:SL.9ClAbsJzqF8rZzbUh7OMfUdWgMEn-Zy5",
                "type": "SequenceLocation",
                "digest": "9ClAbsJzqF8rZzbUh7OMfUdWgMEn-Zy5",
                "sequenceReference": {
                    "type": "SequenceReference",
                    "refgetAccession": "SQ.Ya6Rs7DHhDeg7YaOSg1EoNi3U_nQ9SvO",
                },
                "start": 1047460,
                "end": 1047461,
            },
            "state": {"type": "LiteralSequenceExpression", "sequence": "T"},
        },
    },
    {
        "label": "intronic_minus",
        "variation_id": "3015875",
        "clinvar_name": "NM_002617.4(PEX10):c.601-65C>T",
        "spdi": "NC_000001.11:2406959:G:A",
        "genomic": {
            "id": "ga4gh:VA.34JOe7-8kxqGRV5WFHbZrp7VlJ-_INLm",
            "type": "Allele",
            "digest": "34JOe7-8kxqGRV5WFHbZrp7VlJ-_INLm",
            "location": {
                "id": "ga4gh:SL.A5jkT7PUVMYscq68Psg5_VSEl1FI_l9v",
                "type": "SequenceLocation",
                "digest": "A5jkT7PUVMYscq68Psg5_VSEl1FI_l9v",
                "sequenceReference": {
                    "type": "SequenceReference",
                    "refgetAccession": "SQ.Ya6Rs7DHhDeg7YaOSg1EoNi3U_nQ9SvO",
                },
                "start": 2406959,
                "end": 2406960,
            },
            "state": {"type": "LiteralSequenceExpression", "sequence": "A"},
        },
    },
    {
        "label": "utr_5_prime",
        "variation_id": "297591",
        "clinvar_name": "NM_000098.2(CPT2):c.-477C>T",
        "spdi": "NC_000001.11:53196466:C:T",
        "genomic": {
            "id": "ga4gh:VA.CgioVWTSxp4Uh9JhXqG8gkQsViL4Q6uI",
            "type": "Allele",
            "digest": "CgioVWTSxp4Uh9JhXqG8gkQsViL4Q6uI",
            "location": {
                "id": "ga4gh:SL.yxI6fXQ-b9uO16rUFxLwB1M-Y639iosS",
                "type": "SequenceLocation",
                "digest": "yxI6fXQ-b9uO16rUFxLwB1M-Y639iosS",
                "sequenceReference": {
                    "type": "SequenceReference",
                    "refgetAccession": "SQ.Ya6Rs7DHhDeg7YaOSg1EoNi3U_nQ9SvO",
                },
                "start": 53196466,
                "end": 53196467,
            },
            "state": {"type": "LiteralSequenceExpression", "sequence": "T"},
        },
    },
    {
        "label": "non_mane_no_compatible",
        "variation_id": "450976",
        "clinvar_name": "NM_001372044.2(SHANK3):c.1112+1G>A",
        "spdi": "NC_000022.11:50679428:G:A",
        "genomic": {
            "id": "ga4gh:VA.rKpaEJAGJVinPM650Tv93NEz4YNfbVp6",
            "type": "Allele",
            "digest": "rKpaEJAGJVinPM650Tv93NEz4YNfbVp6",
            "location": {
                "id": "ga4gh:SL.6K3A5ucWCCle2FkPb7uRqFJ9LsV1Kp-z",
                "type": "SequenceLocation",
                "digest": "6K3A5ucWCCle2FkPb7uRqFJ9LsV1Kp-z",
                "sequenceReference": {
                    "type": "SequenceReference",
                    "refgetAccession": "SQ.7B7SHsmchAR0dFcDCuSFjJAo7tX87krQ",
                },
                "start": 50679428,
                "end": 50679429,
            },
            "state": {"type": "LiteralSequenceExpression", "sequence": "A"},
        },
    },
    {
        "label": "non_mane_has_longest_compatible",
        "variation_id": "726125",
        "clinvar_name": "NM_015691.5(WWC3):c.1569G>A (p.Pro523=)",
        "spdi": "NC_000023.11:10117252:G:A",
        "genomic": {
            "id": "ga4gh:VA.FLM1jXSy4gk1MIn0hdM9O4YK8whGHuNS",
            "type": "Allele",
            "digest": "FLM1jXSy4gk1MIn0hdM9O4YK8whGHuNS",
            "location": {
                "id": "ga4gh:SL.mDhVo__TaKQa738CA3kdoYwWuexfSHnw",
                "type": "SequenceLocation",
                "digest": "mDhVo__TaKQa738CA3kdoYwWuexfSHnw",
                "sequenceReference": {
                    "type": "SequenceReference",
                    "refgetAccession": "SQ.w0WZEvgJF0zf_P4yyTzjjv9oW1z61HHP",
                },
                "start": 10117252,
                "end": 10117253,
            },
            "state": {"type": "LiteralSequenceExpression", "sequence": "A"},
        },
    },
]

UTR_PROJECTION_CASES = [
    {
        "label": "utr_5_prime",
        "spdi": "NC_000023.11:100408638:T:",
        "expected_transcript_accession": "NM_001184880.2",
        "expected_transcript_start": 1634,
        "expected_transcript_end": 1635,
    },
    {
        "label": "utr_3_prime",
        "spdi": "NC_000002.12:63122000:A:G",
        "expected_transcript_accession": "NM_015910.7",
        "expected_transcript_start": 2451,
        "expected_transcript_end": 2452,
    },
]


def _assert_forward_mapping(restapi_client, source_id, mapping_type, dest_id):
    response = restapi_client.get(f"/object/{source_id}/mappings/{mapping_type}")
    assert response.status_code == HTTPStatus.OK
    assert response.json() == {
        "mappings": [
            {
                "source_id": source_id,
                "dest_id": dest_id,
                "mapping_type": mapping_type,
            }
        ]
    }


def _assert_no_forward_mapping(restapi_client, source_id, mapping_type):
    response = restapi_client.get(f"/object/{source_id}/mappings/{mapping_type}")
    assert response.status_code == HTTPStatus.OK
    assert response.json() == {"mappings": []}


@pytest.mark.parametrize("projection_case", PROJECTION_CASES, ids=lambda c: c["label"])
def test_spdi_projection_persists_mappings(projected_restapi_client, projection_case):
    """Register a genomic SPDI and verify persisted transcript/protein projections."""
    genomic = projection_case["genomic"]
    transcript = projection_case["transcript"]
    protein = projection_case["protein"]
    expected_messages = projection_case["messages"]

    response = projected_restapi_client.put(
        "/variation", json={"definition": projection_case["spdi"]}
    )
    assert response.status_code == HTTPStatus.OK
    assert response.json() == {
        "input_variation": {
            "definition": projection_case["spdi"],
            "assembly_name": "GRCh38",
        },
        "object": genomic,
        "object_id": genomic["id"],
        "messages": expected_messages,
    }

    _assert_forward_mapping(
        projected_restapi_client,
        genomic["id"],
        metadata.VariationMappingType.TRANSCRIBE_TO,
        transcript["id"],
    )

    response = projected_restapi_client.get(f"/object/{transcript['id']}")
    assert response.status_code == HTTPStatus.OK
    assert response.json() == {"data": transcript, "messages": []}

    if protein:
        _assert_forward_mapping(
            projected_restapi_client,
            transcript["id"],
            metadata.VariationMappingType.TRANSLATE_TO,
            protein["id"],
        )

        response = projected_restapi_client.get(f"/object/{protein['id']}")
        assert response.status_code == HTTPStatus.OK
        assert response.json() == {"data": protein, "messages": []}
    else:
        _assert_no_forward_mapping(
            projected_restapi_client,
            transcript["id"],
            metadata.VariationMappingType.TRANSLATE_TO,
        )

    response = projected_restapi_client.post(
        "/variation", json={"definition": projection_case["spdi"]}
    )
    assert response.status_code == HTTPStatus.OK
    assert response.json() == {"data": genomic, "messages": []}

    _assert_forward_mapping(
        projected_restapi_client,
        genomic["id"],
        metadata.VariationMappingType.TRANSCRIBE_TO,
        transcript["id"],
    )
    if protein:
        _assert_forward_mapping(
            projected_restapi_client,
            transcript["id"],
            metadata.VariationMappingType.TRANSLATE_TO,
            protein["id"],
        )
    else:
        _assert_no_forward_mapping(
            projected_restapi_client,
            transcript["id"],
            metadata.VariationMappingType.TRANSLATE_TO,
        )


@pytest.mark.parametrize(
    "projection_case", NO_MANE_PROJECTION_CASES, ids=lambda c: c["label"]
)
def test_spdi_projection_skips_cases_without_mane_transcripts(
    projected_restapi_client, projection_case
):
    """Register logged ClinVar SPDI cases that do not resolve to MANE transcripts."""
    genomic = projection_case["genomic"]

    response = projected_restapi_client.put(
        "/variation", json={"definition": projection_case["spdi"]}
    )
    assert response.status_code == HTTPStatus.OK
    assert response.json() == {
        "input_variation": {
            "definition": projection_case["spdi"],
            "assembly_name": "GRCh38",
        },
        "object": genomic,
        "object_id": genomic["id"],
        "messages": [],
    }

    response = projected_restapi_client.get(f"/object/{genomic['id']}")
    assert response.status_code == HTTPStatus.OK
    assert response.json() == {"data": genomic, "messages": []}

    _assert_no_forward_mapping(
        projected_restapi_client,
        genomic["id"],
        metadata.VariationMappingType.TRANSCRIBE_TO,
    )

    response = projected_restapi_client.post(
        "/variation", json={"definition": projection_case["spdi"]}
    )
    assert response.status_code == HTTPStatus.OK
    assert response.json() == {"data": genomic, "messages": []}


@pytest.mark.parametrize("utr_case", UTR_PROJECTION_CASES, ids=lambda c: c["label"])
def test_spdi_projection_persists_utr_transcript_without_protein_mapping(
    projected_restapi_client, utr_case
):
    """UTR variants get a transcript mapping but no protein mapping."""
    spdi = utr_case["spdi"]
    expected_start = utr_case["expected_transcript_start"]
    expected_end = utr_case["expected_transcript_end"]
    expected_accession = utr_case["expected_transcript_accession"]

    response = projected_restapi_client.put("/variation", json={"definition": spdi})
    assert response.status_code == HTTPStatus.OK
    payload = response.json()
    assert (
        f"Could not build coding variant for {expected_accession}"
        not in payload["messages"]
    )

    genomic_id = payload["object_id"]
    mapping_response = projected_restapi_client.get(
        f"/object/{genomic_id}/mappings/{metadata.VariationMappingType.TRANSCRIBE_TO}"
    )
    assert mapping_response.status_code == HTTPStatus.OK
    mappings = mapping_response.json()["mappings"]
    assert len(mappings) == 1

    transcript_id = mappings[0]["dest_id"]
    transcript_response = projected_restapi_client.get(f"/object/{transcript_id}")
    assert transcript_response.status_code == HTTPStatus.OK
    transcript = transcript_response.json()["data"]
    assert transcript["location"]["start"] == expected_start
    assert transcript["location"]["end"] == expected_end

    _assert_no_forward_mapping(
        projected_restapi_client,
        transcript_id,
        metadata.VariationMappingType.TRANSLATE_TO,
    )
