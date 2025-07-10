from anyvar.utils.functions import LIFTOVER_ERROR_ANNOTATIONS, LiftoverError

test_variants = {
    "copynumber_ranged_positive_grch37_variant": {
        "variant_input": {
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
        "expected_output": {
            "id": "ga4gh:CN.LQAMim_Q7_sXVRLX2UFVsHNOolDsK4Bo",
            "type": "CopyNumberCount",
            "name": None,
            "description": None,
            "aliases": None,
            "extensions": None,
            "digest": "LQAMim_Q7_sXVRLX2UFVsHNOolDsK4Bo",
            "expressions": None,
            "location": {
                "id": "ga4gh:SL.7HsIbSybxJRfiRNr2r0gz1JNsV-wJJfQ",
                "type": "SequenceLocation",
                "name": None,
                "description": None,
                "aliases": None,
                "extensions": None,
                "digest": "7HsIbSybxJRfiRNr2r0gz1JNsV-wJJfQ",
                "sequenceReference": {
                    "id": None,
                    "type": "SequenceReference",
                    "name": None,
                    "description": None,
                    "aliases": None,
                    "extensions": None,
                    "refgetAccession": "SQ.-A1QmD_MatoqxvgVxBLZTONHz9-c7nQo",
                    "residueAlphabet": None,
                    "circular": None,
                    "sequence": None,
                    "moleculeType": None,
                },
                "start": [None, 30417575],
                "end": [31394018, None],
                "sequence": None,
            },
            "copies": 3,
        },
    },
    "allele_int_negative_grch38_variant": {  # BRAF V600E
        "variant_input": {
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
        "expected_output": {
            "aliases": None,
            "description": None,
            "digest": "dvp7PZ4uKIb9L7IpieJewYSTkgpXgaza",
            "expressions": None,
            "extensions": None,
            "id": "ga4gh:VA.dvp7PZ4uKIb9L7IpieJewYSTkgpXgaza",
            "location": {
                "aliases": None,
                "description": None,
                "digest": "hVna-JOV5bBTGdXexL--IQm135MG3bGT",
                "end": 140453136,
                "extensions": None,
                "id": "ga4gh:SL.hVna-JOV5bBTGdXexL--IQm135MG3bGT",
                "name": None,
                "sequence": None,
                "sequenceReference": {
                    "aliases": None,
                    "circular": None,
                    "description": None,
                    "extensions": None,
                    "id": None,
                    "moleculeType": None,
                    "name": None,
                    "refgetAccession": "SQ.IW78mgV5Cqf6M24hy52hPjyyo5tCCd86",
                    "residueAlphabet": None,
                    "sequence": None,
                    "type": "SequenceReference",
                },
                "start": 140453135,
                "type": "SequenceLocation",
            },
            "name": None,
            "state": {
                "aliases": None,
                "description": None,
                "extensions": None,
                "id": None,
                "name": None,
                "sequence": "T",
                "type": "LiteralSequenceExpression",
            },
            "type": "Allele",
        },
    },
    "allele_int_unknown_grch38_variant": {
        "variant_input": {
            "id": "ga4gh: VA.9gW_iJbQAIO3SIxJ9ACyAZA1X2lEgO39",
            "digest": "9gW_iJbQAIO3SIxJ9ACyAZA1X2lEgO39",
            "type": "Allele",
            "location": {
                "id": "ga4gh: SL.sK161kPiQBsm-qOErlsNRXeT3nvoTLLn",
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
        "expected_output": {
            "aliases": None,
            "description": None,
            "digest": "FTRS8BT4hXgVVOnbq4rGPqQo5tZInhoP",
            "expressions": None,
            "extensions": None,
            "id": "ga4gh:VA.FTRS8BT4hXgVVOnbq4rGPqQo5tZInhoP",
            "location": {
                "aliases": None,
                "description": None,
                "digest": "yuqVJ7v6Q1h7-oXiyVToQn0AsukMMRb8",
                "end": 178921549,
                "extensions": None,
                "id": "ga4gh:SL.yuqVJ7v6Q1h7-oXiyVToQn0AsukMMRb8",
                "name": None,
                "sequence": None,
                "sequenceReference": {
                    "aliases": None,
                    "circular": None,
                    "description": None,
                    "extensions": None,
                    "id": None,
                    "moleculeType": None,
                    "name": None,
                    "refgetAccession": "SQ.VNBualIltAyi2AI_uXcKU7M9XUOuA7MS",
                    "residueAlphabet": None,
                    "sequence": None,
                    "type": "SequenceReference",
                },
                "start": 178921548,
                "type": "SequenceLocation",
            },
            "name": None,
            "state": {
                "aliases": None,
                "description": None,
                "extensions": None,
                "id": None,
                "name": None,
                "sequence": "G",
                "type": "LiteralSequenceExpression",
            },
            "type": "Allele",
        },
    },  # FAILURES
    "grch36_variant": {  # Variant that's on an unsupported assembly (GRCh36)
        "variant_input": {
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
        "expected_output": LIFTOVER_ERROR_ANNOTATIONS[
            LiftoverError.UNSUPPORTED_REFERENCE_ASSEMBLY
        ],
    },
    # "unconvertible_grch37_variant": {
    # 	"variant_input": {},
    #     "expected_output": LIFTOVER_ERROR_ANNOTATIONS[
    #         LiftoverError.ACCESSION_CONVERSION_ERROR
    #     ],
    # },
    "empty_variation_object": {
        "variant_input": {},
        "expected_output": LIFTOVER_ERROR_ANNOTATIONS[LiftoverError.INPUT_ERROR],
    },
}


# STILL NEED:
# - A variant that exists on GRCh37 but not GRCH38
# - A variant that exists on GRCh38 but not GRCH37
# - A variant with a "location" type that's not "SequenceLocation"
# - A variant where the chromosome can't be determined?? (Is this even a thing?)
