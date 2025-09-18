from ga4gh.vrs import models

from anyvar.utils.liftover_utils import (
    CoordinateConversionFailureError,
    ReverseLiftoverError,
    UnsupportedReferenceAssemblyError,
)

test_variants = {
    "copynumber_ranged_positive_grch37_variant": {
        "input_variant": {
            "id": "ga4gh:CN.CTCgVehH0FEqrlaOMhUsDjKwzavnQegk",
            "type": "CopyNumberCount",
            "location": {
                "sequenceReference": {
                    "type": "SequenceReference",
                    "refgetAccession": "SQ.iy_UbUrvECxFRX5LPTH_KPojdlT7BKsf",
                },
                "start": [None, 29652251],
                "end": [29981821, None],
                "type": "SequenceLocation",
            },
            "copies": 3,
        },
        "expected_liftover_output": models.CopyNumberCount(
            id="ga4gh:CN.LQAMim_Q7_sXVRLX2UFVsHNOolDsK4Bo",
            digest="LQAMim_Q7_sXVRLX2UFVsHNOolDsK4Bo",
            type="CopyNumberCount",
            location=models.SequenceLocation(
                id="ga4gh:SL.7HsIbSybxJRfiRNr2r0gz1JNsV-wJJfQ",
                type="SequenceLocation",
                digest="7HsIbSybxJRfiRNr2r0gz1JNsV-wJJfQ",
                sequenceReference=models.SequenceReference(
                    type="SequenceReference",
                    refgetAccession="SQ.-A1QmD_MatoqxvgVxBLZTONHz9-c7nQo",
                ),  # type: ignore[reportAssignmentType]
                start=models.Range([None, 30417575]),
                end=models.Range([31394018, None]),
            ),  # type: ignore[reportAssignmentType]
            copies=3,
        ),  # type: ignore[reportAssignmentType]
        "expected_reverse_liftover_annotation": "ga4gh:CN.CTCgVehH0FEqrlaOMhUsDjKwzavnQegk",
    },
    # BRAF V600E
    "allele_int_negative_grch38_variant": {
        "input_variant": {
            "id": "ga4gh:VA.Otc5ovrw906Ack087o1fhegB4jDRqCAe",
            "type": "Allele",
            "digest": "Otc5ovrw906Ack087o1fhegB4jDRqCAe",
            "location": {
                "id": "ga4gh:SL.nhul5x5P_fKjGEpY9PEkMIekJfZaKom2",
                "type": "SequenceLocation",
                "digest": "nhul5x5P_fKjGEpY9PEkMIekJfZaKom2",
                "sequenceReference": {
                    "type": "SequenceReference",
                    "refgetAccession": "SQ.F-LrLMe1SRpfUZHkQmvkVKFEGaoDeHul",
                },
                "start": 140753335,
                "end": 140753336,
            },
            "state": {"type": "LiteralSequenceExpression", "sequence": "T"},
        },
        "expected_liftover_output": models.Allele(
            digest="dvp7PZ4uKIb9L7IpieJewYSTkgpXgaza",
            id="ga4gh:VA.dvp7PZ4uKIb9L7IpieJewYSTkgpXgaza",
            type="Allele",
            location=models.SequenceLocation(
                digest="hVna-JOV5bBTGdXexL--IQm135MG3bGT",
                end=140453136,
                id="ga4gh:SL.hVna-JOV5bBTGdXexL--IQm135MG3bGT",
                sequenceReference=models.SequenceReference(
                    refgetAccession="SQ.IW78mgV5Cqf6M24hy52hPjyyo5tCCd86",
                    type="SequenceReference",
                ),  # type: ignore[reportAssignmentType]
                start=140453135,
                type="SequenceLocation",
            ),
            state=models.LiteralSequenceExpression(
                sequence=models.sequenceString("T"),
                type="LiteralSequenceExpression",
            ),  # type: ignore[reportAssignmentType]
        ),
        "expected_reverse_liftover_annotation": ReverseLiftoverError(
            "ga4gh:VA.Au4CvWQcjNe4wXU3SDo2Xtb94cv5Bgoh",
            "ga4gh:VA.Otc5ovrw906Ack087o1fhegB4jDRqCAe",
        ).error_details,
    },
    "allele_int_unknown_grch38_variant": {
        "input_variant": {
            "id": "ga4gh:VA.9gW_iJbQAIO3SIxJ9ACyAZA1X2lEgO39",
            "digest": "9gW_iJbQAIO3SIxJ9ACyAZA1X2lEgO39",
            "type": "Allele",
            "location": {
                "id": "ga4gh:SL.sK161kPiQBsm-qOErlsNRXeT3nvoTLLn",
                "digest": "sK161kPiQBsm-qOErlsNRXeT3nvoTLLn",
                "sequenceReference": {
                    "refgetAccession": "SQ.Zu7h9AggXxhTaGVsy7h_EZSChSZGcmgX",
                    "type": "SequenceReference",
                },
                "start": 179203760,
                "end": 179203761,
                "type": "SequenceLocation",
            },
            "state": {"sequence": "G", "type": "LiteralSequenceExpression"},
        },
        "expected_liftover_output": models.Allele(
            digest="FTRS8BT4hXgVVOnbq4rGPqQo5tZInhoP",
            id="ga4gh:VA.FTRS8BT4hXgVVOnbq4rGPqQo5tZInhoP",
            location=models.SequenceLocation(
                digest="yuqVJ7v6Q1h7-oXiyVToQn0AsukMMRb8",
                end=178921549,
                id="ga4gh:SL.yuqVJ7v6Q1h7-oXiyVToQn0AsukMMRb8",
                sequenceReference=models.SequenceReference(
                    refgetAccession="SQ.VNBualIltAyi2AI_uXcKU7M9XUOuA7MS",
                    type="SequenceReference",
                ),  # type: ignore[reportAssignmentType]
                start=178921548,
                type="SequenceLocation",
            ),
            state=models.LiteralSequenceExpression(
                sequence=models.sequenceString("G"),
                type="LiteralSequenceExpression",
            ),  # type: ignore[reportAssignmentType]
            type="Allele",
        ),
        "expected_reverse_liftover_annotation": ReverseLiftoverError(
            "ga4gh:VA.RNgtXtdPKTKdHhUQsBCdHsPrtbPRBmAO",
            "ga4gh:VA.9gW_iJbQAIO3SIxJ9ACyAZA1X2lEgO39",
        ).error_details,
    },  # FAILURES
    "grch36_variant": {  # Variant that's on an unsupported assembly (GRCh36)
        "input_variant": {
            "digest": "4dEsVNR2JC_ZiHsYSGZgariIUOfYl6a0",
            "id": "ga4gh:VA.4dEsVNR2JC_ZiHsYSGZgariIUOfYl6a0",
            "type": "Allele",
            "location": {
                "id": "ga4gh:SL.WROR90lhzJwgTPgxZx8dRP4Vcjr3BdDi",
                "digest": "WROR90lhzJwgTPgxZx8dRP4Vcjr3BdDi",
                "type": "SequenceLocation",
                "start": 45103598,
                "end": 45103599,
                "sequenceReference": {
                    "refgetAccession": "SQ.JY7UegcaYT-M0PYn1yDGQ_4XJsa-DsXq",
                    "type": "SequenceReference",
                },
            },
            "state": {"sequence": "T", "type": "LiteralSequenceExpression"},
        },
        "expected_liftover_output": UnsupportedReferenceAssemblyError,
        "expected_reverse_liftover_annotation": None,
    },
    "unconvertible_grch37_variant": {
        "input_variant": {
            "id": "ga4gh:VA.qP-qtMJqKhTEJfpTdAZN9CoIFCRKv4kg",
            "type": "Allele",
            "digest": "qP-qtMJqKhTEJfpTdAZN9CoIFCRKv4kg",
            "location": {
                "id": "ga4gh:SL.VqjvHF-g0sA8syECkQvnsVlK66zHtrHU",
                "type": "SequenceLocation",
                "digest": "VqjvHF-g0sA8syECkQvnsVlK66zHtrHU",
                "sequenceReference": {
                    "type": "SequenceReference",
                    "refgetAccession": "SQ.-BOZ8Esn8J88qDwNiSEwUr5425UXdiGX",
                },
                "start": 47087473,
                "end": 47087474,
            },
            "state": {"type": "LiteralSequenceExpression", "sequence": "T"},
        },
        "expected_liftover_output": CoordinateConversionFailureError,
        "expected_reverse_liftover_annotation": None,
    },
    "unconvertible_grch38_variant": {  # see: https://www.ncbi.nlm.nih.gov/clinvar/variation/3035826/?oq=NC_000017.11:50150040:GC:GCGC&m=NM_032595.5(PPP1R9B):c.472_473dup%20(p.Ala159fs)
        "input_variant": {
            "digest": "5-m9wM6WTY5osPxLFg1_bITsOwSoMFui",
            "id": "ga4gh:VA.5-m9wM6WTY5osPxLFg1_bITsOwSoMFui",
            "location": {
                "digest": "IvygUHxpbRf558JG7ZuPYZrZhL_eMp0O",
                "end": 50150042,
                "id": "ga4gh:SL.IvygUHxpbRf558JG7ZuPYZrZhL_eMp0O",
                "sequenceReference": {
                    "refgetAccession": "SQ.dLZ15tNO1Ur0IcGjwc3Sdi_0A6Yf4zm7",
                    "type": "SequenceReference",
                },
                "start": 50150040,
                "type": "SequenceLocation",
            },
            "state": {
                "length": 4,
                "repeatSubunitLength": 2,
                "sequence": "GCGC",
                "type": "ReferenceLengthExpression",
            },
            "type": "Allele",
        },
        "expected_liftover_output": CoordinateConversionFailureError,
        "expected_reverse_liftover_annotation": None,
    },
    "empty_variation_object": {
        "input_variant": {},
        "expected_liftover_output": None,
        "expected_reverse_liftover_annotation": None,
    },
    "invalid_variant": {
        "input_variant": {
            "location": {
                "id": "ga4gh:SL.aCMcqLGKClwMWEDx3QWe4XSiGDlKXdB8",
                "end": 0,
                "start": -1,
                "sequenceReference": {
                    "refgetAccession": "SQ.ss8r_wB0-b9r44TQTMmVTI92884QvBiB",
                    "type": "SequenceReference",
                },
                "type": "SequenceLocation",
            },
            "state": {"sequence": "T", "type": "LiteralSequenceExpression"},
            "type": "UNSUPPORTED",
        },
        "expected_liftover_output": None,
        "expected_reverse_liftover_annotation": None,
    },
}


# STILL NEED:
# - A variant that exists on GRCh38 but not GRCH37
# - A CopyNumberCount variant?
