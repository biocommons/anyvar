"""Unit tests for projection internals."""

# ruff: noqa: SLF001

from types import SimpleNamespace

import pytest
from ga4gh.vrs import models

from anyvar.mapping import projection


class FakeDataProxy:
    _REFGET_ACCESSION = "SQ.AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"

    def __init__(self):
        self.sequence_calls: list[tuple[str, int, int]] = []

    def translate_sequence_identifier(
        self, _accession: str, target_namespace: str
    ) -> list[str]:
        if target_namespace != "ga4gh":
            msg = f"unexpected namespace: {target_namespace}"
            raise AssertionError(msg)
        return [f"ga4gh:{self._REFGET_ACCESSION}"]

    def get_sequence(self, identifier: str, start: int, end: int) -> str:
        self.sequence_calls.append((identifier, start, end))
        return "A" * (end - start)


class FakeFuture:
    def __init__(self, result):
        self._result = result

    def result(self, timeout: int):
        _ = timeout
        return self._result


def test_build_allele_normalizes_projected_literal_state(mocker):
    dp = FakeDataProxy()
    state = models.LiteralSequenceExpression(
        type="LiteralSequenceExpression",
        sequence="T",
    )
    normalize_mock = mocker.patch.object(
        projection,
        "normalize",
        side_effect=lambda allele, **_kwargs: allele,
    )

    allele = projection._build_allele(
        dp,
        "NM_001184880.2",
        857,
        888,
        state,
    )

    normalize_mock.assert_called_once()
    assert normalize_mock.call_args.kwargs == {"data_proxy": dp}
    assert dp.sequence_calls == []
    assert allele.type == "Allele"
    assert allele.location.type == "SequenceLocation"
    assert allele.location.sequenceReference.refgetAccession == dp._REFGET_ACCESSION
    assert allele.location.start == 857
    assert allele.location.end == 888
    assert allele.state == state


def test_project_cdna_literal_state_reverse_complements_negative_strand_literal_state():
    dp = FakeDataProxy()
    variation = SimpleNamespace(
        id="ga4gh:VA.input",
        state=models.LiteralSequenceExpression(
            type="LiteralSequenceExpression",
            sequence="A",
        ),
    )
    cdna = SimpleNamespace(strand=SimpleNamespace(value=-1))

    state = projection._project_cdna_literal_state(dp, variation, cdna)

    assert state == models.LiteralSequenceExpression(
        type="LiteralSequenceExpression",
        sequence="T",
    )


def test_project_cdna_literal_state_expands_positive_strand_reference_length_state():
    dp = FakeDataProxy()
    variation = SimpleNamespace(
        id="ga4gh:VA.input",
        state=models.ReferenceLengthExpression(
            type="ReferenceLengthExpression",
            length=3,
            sequence="CTC",
            repeatSubunitLength=2,
        ),
    )
    cdna = SimpleNamespace(strand=SimpleNamespace(value=1))

    state = projection._project_cdna_literal_state(dp, variation, cdna)

    assert state == models.LiteralSequenceExpression(
        type="LiteralSequenceExpression",
        sequence="CTC",
    )


def test_project_cdna_literal_state_reverse_complements_negative_strand_rle_sequence():
    dp = FakeDataProxy()
    variation = SimpleNamespace(
        id="ga4gh:VA.input",
        state=models.ReferenceLengthExpression(
            type="ReferenceLengthExpression",
            length=3,
            sequence="CTC",
            repeatSubunitLength=2,
        ),
    )
    cdna = SimpleNamespace(strand=SimpleNamespace(value=-1))

    state = projection._project_cdna_literal_state(dp, variation, cdna)

    assert state == models.LiteralSequenceExpression(
        type="LiteralSequenceExpression",
        sequence="GAG",
    )


def test_project_cdna_literal_state_expands_rle_without_embedded_sequence(mocker):
    dp = FakeDataProxy()
    dp.get_sequence = mocker.Mock(return_value="CTCTC")
    denormalize_mock = mocker.patch.object(
        projection,
        "denormalize_reference_length_expression",
        return_value="CTC",
    )
    variation = SimpleNamespace(
        id="ga4gh:VA.input",
        state=models.ReferenceLengthExpression(
            type="ReferenceLengthExpression",
            length=3,
            repeatSubunitLength=2,
        ),
        location=SimpleNamespace(
            sequenceReference=SimpleNamespace(refgetAccession="SQ.genomic"),
            start=10,
            end=15,
        ),
    )
    cdna = SimpleNamespace(strand=SimpleNamespace(value=1))

    state = projection._project_cdna_literal_state(dp, variation, cdna)

    dp.get_sequence.assert_called_once_with("ga4gh:SQ.genomic", start=10, end=15)
    denormalize_mock.assert_called_once_with("CTCTC", 2, 3)
    assert state == models.LiteralSequenceExpression(
        type="LiteralSequenceExpression",
        sequence="CTC",
    )


def test_project_cdna_literal_state_raises_projection_error_when_helper_fails(mocker):
    dp = FakeDataProxy()
    variation = SimpleNamespace(
        id="ga4gh:VA.input",
        state=models.LiteralSequenceExpression(
            type="LiteralSequenceExpression",
            sequence="A",
        ),
    )
    cdna = SimpleNamespace(strand=SimpleNamespace(value=-1))
    mocker.patch.object(
        projection.bioutils_sequences,
        "reverse_complement",
        side_effect=ValueError("bad sequence"),
    )

    with pytest.raises(projection.ProjectionError):
        projection._project_cdna_literal_state(dp, variation, cdna)


def test_derive_protein_substitution_state_uses_bioutils_translate_cds(mocker):
    dp = FakeDataProxy()
    mocker.patch.object(dp, "get_sequence", return_value="ATG")
    translate_cds = mocker.patch.object(
        projection.bioutils_sequences,
        "translate_cds",
        return_value="L",
    )
    cdna = SimpleNamespace(refseq="NM_004333.6", coding_start_site=200)
    protein = SimpleNamespace(refseq="NP_004324.2", pos=(0, 1))
    cdna_state = models.LiteralSequenceExpression(
        type="LiteralSequenceExpression",
        sequence="T",
    )

    state = projection._derive_protein_substitution_state(
        dp,
        cdna,
        protein,
        200,
        201,
        cdna_state,
    )

    translate_cds.assert_called_once_with("TTG", full_codons=True, ter_symbol="*")
    assert state == models.LiteralSequenceExpression(
        type="LiteralSequenceExpression",
        sequence="L",
    )


def test_derive_protein_substitution_state_raises_projection_error_for_indel():
    dp = FakeDataProxy()
    cdna = SimpleNamespace(refseq="NM_004333.6", coding_start_site=200)
    protein = SimpleNamespace(refseq="NP_004324.2", pos=(0, 1))
    cdna_state = models.LiteralSequenceExpression(
        type="LiteralSequenceExpression",
        sequence="AT",
    )

    with pytest.raises(
        projection.ProjectionError,
        match="Projection skipped: could not derive alternate protein state",
    ):
        projection._derive_protein_substitution_state(
            dp,
            cdna,
            protein,
            200,
            201,
            cdna_state,
        )


def test_store_projected_variant_only_persists_forward_mapping(mocker):
    storage = mocker.Mock()
    projected_variant = SimpleNamespace(id="ga4gh:VA.projected")

    projection._store_projected_variant(
        storage,
        "ga4gh:VA.source",
        projected_variant,
        projection.VariationMappingType.TRANSLATE_TO,
    )

    storage.add_objects.assert_called_once_with([projected_variant])
    storage.add_mapping.assert_called_once_with(
        projection.VariationMapping(
            source_id="ga4gh:VA.source",
            dest_id="ga4gh:VA.projected",
            mapping_type=projection.VariationMappingType.TRANSLATE_TO,
        )
    )


class TestIsUtrVariant:
    """Tests for _is_utr_variant helper."""

    def test_5_prime_utr(self):
        cdna = SimpleNamespace(
            pos=(-477, -476), coding_start_site=200, coding_end_site=2200
        )
        assert projection._is_utr_variant(cdna) == "5_prime"

    def test_3_prime_utr(self):
        cdna = SimpleNamespace(
            pos=(2100, 2101), coding_start_site=200, coding_end_site=2200
        )
        assert projection._is_utr_variant(cdna) == "3_prime"

    def test_cds_variant(self):
        cdna = SimpleNamespace(
            pos=(100, 101), coding_start_site=200, coding_end_site=2200
        )
        assert projection._is_utr_variant(cdna) is None

    def test_boundary_spanning_5_prime(self):
        """Variant spanning 5' UTR/CDS boundary is flagged as UTR."""
        cdna = SimpleNamespace(pos=(-5, 3), coding_start_site=200, coding_end_site=2200)
        assert projection._is_utr_variant(cdna) == "5_prime"

    def test_boundary_spanning_3_prime(self):
        """Variant spanning CDS/3' UTR boundary is flagged as UTR."""
        cdna = SimpleNamespace(
            pos=(1998, 2003), coding_start_site=200, coding_end_site=2200
        )
        assert projection._is_utr_variant(cdna) == "3_prime"

    def test_exact_boundary_5_prime(self):
        """Variant ending exactly at CDS start (pos[1]=0) is entirely 5' UTR."""
        cdna = SimpleNamespace(pos=(-1, 0), coding_start_site=200, coding_end_site=2200)
        assert projection._is_utr_variant(cdna) == "5_prime"

    def test_exact_boundary_3_prime(self):
        """Variant starting exactly at CDS end extends into 3' UTR."""
        cdna = SimpleNamespace(
            pos=(2000, 2001), coding_start_site=200, coding_end_site=2200
        )
        assert projection._is_utr_variant(cdna) == "3_prime"

    def test_variant_at_cds_start(self):
        """Variant starting at position 0 (CDS start) is NOT UTR."""
        cdna = SimpleNamespace(pos=(0, 1), coding_start_site=200, coding_end_site=2200)
        assert projection._is_utr_variant(cdna) is None

    def test_insertion_before_cds_start(self):
        """Insertion at the CDS start boundary is in the 5' UTR."""
        cdna = SimpleNamespace(pos=(0, 0), coding_start_site=200, coding_end_site=2200)
        assert projection._is_utr_variant(cdna) == "5_prime"

    def test_variant_at_cds_end(self):
        """Variant ending exactly at CDS end is NOT UTR (inter-residue end is exclusive)."""
        cdna = SimpleNamespace(
            pos=(1999, 2000), coding_start_site=200, coding_end_site=2200
        )
        assert projection._is_utr_variant(cdna) is None

    def test_insertion_after_cds_end(self):
        """Insertion at the CDS end boundary is in the 3' UTR."""
        cdna = SimpleNamespace(
            pos=(2000, 2000), coding_start_site=200, coding_end_site=2200
        )
        assert projection._is_utr_variant(cdna) == "3_prime"

    def test_insertion_within_cds(self):
        """Insertion within CDS is not classified as UTR."""
        cdna = SimpleNamespace(
            pos=(1000, 1000), coding_start_site=200, coding_end_site=2200
        )
        assert projection._is_utr_variant(cdna) is None


def test_project_genomic_variant_skips_protein_for_5_prime_utr(mocker):
    """5' UTR variant gets transcript mapping but no protein mapping."""
    result = SimpleNamespace(
        cdna=SimpleNamespace(
            refseq="NM_001184880.2",
            pos=(-1143, -1112),
            coding_start_site=2000,
            coding_end_site=4000,
        ),
        protein=SimpleNamespace(
            refseq="NP_001171809.1",
            pos=(-381, -370),
        ),
    )

    mocker.patch.object(
        projection, "_get_refseq_accession", return_value="NC_000023.11"
    )
    mocker.patch.object(
        projection.asyncio,
        "run_coroutine_threadsafe",
        return_value=FakeFuture(result),
    )

    build_calls = []

    def fake_build_allele(_dp, refseq_accession, _start, _end, _state):
        build_calls.append(refseq_accession)
        return SimpleNamespace(id=f"ga4gh:VA.{refseq_accession}")

    mocker.patch.object(projection, "_build_allele", side_effect=fake_build_allele)
    store_mock = mocker.patch.object(projection, "_store_projected_variant")

    projector = object.__new__(projection.VariantProjector)
    projector.cst = SimpleNamespace(
        mane_transcript=SimpleNamespace(grch38_to_mane_c_p=lambda **kw: None)
    )
    projector.dp = object()
    projector._loop = object()

    variation = SimpleNamespace(
        id="ga4gh:VA.input",
        state=models.LiteralSequenceExpression(
            type="LiteralSequenceExpression",
            sequence="",
        ),
        location=SimpleNamespace(
            sequenceReference=SimpleNamespace(refgetAccession="SQ.genomic"),
            start=100408638,
            end=100408639,
        ),
    )

    messages = projector._project_genomic_variant(variation, mocker.Mock())

    assert messages is None
    assert build_calls == ["NM_001184880.2"]
    store_mock.assert_called_once()


def test_project_genomic_variant_skips_protein_for_3_prime_utr(mocker):
    """3' UTR variant gets transcript mapping but no protein mapping."""
    result = SimpleNamespace(
        cdna=SimpleNamespace(
            refseq="NM_015910.7",
            pos=(2100, 2101),
            coding_start_site=200,
            coding_end_site=2200,
        ),
        protein=SimpleNamespace(
            refseq="NP_056994.1",
            pos=(700, 701),
        ),
    )

    mocker.patch.object(
        projection, "_get_refseq_accession", return_value="NC_000002.12"
    )
    mocker.patch.object(
        projection.asyncio,
        "run_coroutine_threadsafe",
        return_value=FakeFuture(result),
    )

    build_calls = []

    def fake_build_allele(_dp, refseq_accession, _start, _end, _state):
        build_calls.append(refseq_accession)
        return SimpleNamespace(id=f"ga4gh:VA.{refseq_accession}")

    mocker.patch.object(projection, "_build_allele", side_effect=fake_build_allele)
    store_mock = mocker.patch.object(projection, "_store_projected_variant")

    projector = object.__new__(projection.VariantProjector)
    projector.cst = SimpleNamespace(
        mane_transcript=SimpleNamespace(grch38_to_mane_c_p=lambda **kw: None)
    )
    projector.dp = object()
    projector._loop = object()

    variation = SimpleNamespace(
        id="ga4gh:VA.input",
        state=models.LiteralSequenceExpression(
            type="LiteralSequenceExpression",
            sequence="G",
        ),
        location=SimpleNamespace(
            sequenceReference=SimpleNamespace(refgetAccession="SQ.genomic"),
            start=63122000,
            end=63122001,
        ),
    )

    messages = projector._project_genomic_variant(variation, mocker.Mock())

    assert messages is None
    assert build_calls == ["NM_015910.7"]
    store_mock.assert_called_once()


def test_project_genomic_variant_creates_protein_for_cds_variant(mocker):
    """CDS variant gets both transcript AND protein mapping."""
    result = SimpleNamespace(
        cdna=SimpleNamespace(
            refseq="NM_004333.6",
            pos=(100, 101),
            coding_start_site=200,
            coding_end_site=2200,
        ),
        protein=SimpleNamespace(
            refseq="NP_004324.2",
            pos=(33, 34),
        ),
    )

    mocker.patch.object(
        projection, "_get_refseq_accession", return_value="NC_000007.14"
    )
    mocker.patch.object(
        projection.asyncio,
        "run_coroutine_threadsafe",
        return_value=FakeFuture(result),
    )

    build_calls = []

    def fake_build_allele(_dp, refseq_accession, _start, _end, _state):
        build_calls.append(refseq_accession)
        return SimpleNamespace(id=f"ga4gh:VA.{refseq_accession}")

    mocker.patch.object(projection, "_build_allele", side_effect=fake_build_allele)
    mocker.patch.object(
        projection,
        "_derive_protein_substitution_state",
        return_value=models.LiteralSequenceExpression(
            type="LiteralSequenceExpression",
            sequence="L",
        ),
    )
    store_mock = mocker.patch.object(projection, "_store_projected_variant")

    projector = object.__new__(projection.VariantProjector)
    projector.cst = SimpleNamespace(
        mane_transcript=SimpleNamespace(grch38_to_mane_c_p=lambda **kw: None)
    )
    projector.dp = object()
    projector._loop = object()

    variation = SimpleNamespace(
        id="ga4gh:VA.input",
        state=models.LiteralSequenceExpression(
            type="LiteralSequenceExpression",
            sequence="A",
        ),
        location=SimpleNamespace(
            sequenceReference=SimpleNamespace(refgetAccession="SQ.genomic"),
            start=140753336,
            end=140753337,
        ),
    )

    messages = projector._project_genomic_variant(variation, mocker.Mock())

    assert messages is None
    assert build_calls == ["NM_004333.6", "NP_004324.2"]
    assert store_mock.call_count == 2


def test_project_genomic_variant_reports_unsupported_protein_state(mocker):
    """Unsupported protein derivation stores transcript mapping with a message."""
    result = SimpleNamespace(
        cdna=SimpleNamespace(
            refseq="NM_004333.6",
            pos=(100, 102),
            coding_start_site=200,
            coding_end_site=2200,
        ),
        protein=SimpleNamespace(
            refseq="NP_004324.2",
            pos=(33, 34),
        ),
    )

    mocker.patch.object(
        projection, "_get_refseq_accession", return_value="NC_000007.14"
    )
    mocker.patch.object(
        projection.asyncio,
        "run_coroutine_threadsafe",
        return_value=FakeFuture(result),
    )

    build_calls = []

    def fake_build_allele(_dp, refseq_accession, _start, _end, _state):
        build_calls.append(refseq_accession)
        return SimpleNamespace(id=f"ga4gh:VA.{refseq_accession}")

    mocker.patch.object(projection, "_build_allele", side_effect=fake_build_allele)
    store_mock = mocker.patch.object(projection, "_store_projected_variant")

    projector = object.__new__(projection.VariantProjector)
    projector.cst = SimpleNamespace(
        mane_transcript=SimpleNamespace(grch38_to_mane_c_p=lambda **kw: None)
    )
    projector.dp = object()
    projector._loop = object()

    variation = SimpleNamespace(
        id="ga4gh:VA.input",
        state=models.ReferenceLengthExpression(
            type="ReferenceLengthExpression",
            length=1,
            sequence="A",
            repeatSubunitLength=1,
        ),
        location=SimpleNamespace(
            sequenceReference=SimpleNamespace(refgetAccession="SQ.genomic"),
            start=140753336,
            end=140753338,
        ),
    )

    messages = projector._project_genomic_variant(variation, mocker.Mock())

    assert messages == [
        "Projection skipped: could not derive alternate protein state for NP_004324.2"
    ]
    assert build_calls == ["NM_004333.6"]
    store_mock.assert_called_once()


def test_add_mappings_returns_projection_error_message(mocker):
    projector = object.__new__(projection.VariantProjector)
    mocker.patch.object(
        projector,
        "_project_genomic_variant",
        side_effect=projection.ProjectionError("Projection failed: expected failure"),
    )
    variation = SimpleNamespace(id="ga4gh:VA.input")

    messages = projector.add_mappings(variation, mocker.Mock())

    assert messages == ["Projection failed: expected failure"]


def test_project_genomic_variant_applies_cdna_coding_start_site_before_build(mocker):
    captured_build_kwargs = []

    def fake_projection(*args, **kwargs):
        return None

    result = SimpleNamespace(
        cdna=SimpleNamespace(
            refseq="NM_001184880.2",
            pos=(-1143, -1112),
            coding_start_site=2000,
            coding_end_site=4000,
        ),
        protein=None,
    )

    mocker.patch.object(
        projection,
        "_get_refseq_accession",
        return_value="NC_000001.11",
    )
    mocker.patch.object(
        projection.asyncio,
        "run_coroutine_threadsafe",
        return_value=FakeFuture(result),
    )

    def fake_build_allele(_dp, refseq_accession, start, end, state):
        captured_build_kwargs.append(
            {
                "refseq_accession": refseq_accession,
                "start": start,
                "end": end,
                "state": state,
            }
        )
        return SimpleNamespace(id="ga4gh:VA.projected")

    store_mock = mocker.patch.object(projection, "_store_projected_variant")
    mocker.patch.object(projection, "_build_allele", side_effect=fake_build_allele)

    projector = object.__new__(projection.VariantProjector)
    projector.cst = SimpleNamespace(
        mane_transcript=SimpleNamespace(grch38_to_mane_c_p=fake_projection)
    )
    projector.dp = object()
    projector._loop = object()

    variation = SimpleNamespace(
        id="ga4gh:VA.input",
        state=models.LiteralSequenceExpression(
            type="LiteralSequenceExpression",
            sequence="T",
        ),
        location=SimpleNamespace(
            sequenceReference=SimpleNamespace(refgetAccession="SQ.genomic"),
            start=53196466,
            end=53196467,
        ),
    )

    messages = projector._project_genomic_variant(variation, mocker.Mock())

    assert messages is None
    assert captured_build_kwargs == [
        {
            "refseq_accession": "NM_001184880.2",
            "start": 857,
            "end": 888,
            "state": models.LiteralSequenceExpression(
                type="LiteralSequenceExpression",
                sequence="T",
            ),
        }
    ]
    store_mock.assert_called_once()
