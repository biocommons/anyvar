"""Unit tests for projection internals."""

# ruff: noqa: SLF001

from types import SimpleNamespace

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


def test_build_allele_uses_absolute_sequence_coordinates():
    dp = FakeDataProxy()

    allele = projection._build_allele(
        dp,
        "NM_001184880.2",
        857,
        888,
    )

    assert dp.sequence_calls == [(f"ga4gh:{dp._REFGET_ACCESSION}", 857, 888)]
    assert allele.type == "Allele"
    assert allele.location.type == "SequenceLocation"
    assert allele.location.sequenceReference.refgetAccession == dp._REFGET_ACCESSION
    assert allele.location.start == 857
    assert allele.location.end == 888
    assert allele.state == models.LiteralSequenceExpression(
        type="LiteralSequenceExpression",
        sequence="A" * 31,
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

    def test_variant_at_cds_end(self):
        """Variant ending exactly at CDS end is NOT UTR (inter-residue end is exclusive)."""
        cdna = SimpleNamespace(
            pos=(1999, 2000), coding_start_site=200, coding_end_site=2200
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

    def fake_build_allele(_dp, refseq_accession, _start, _end, **kwargs):
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

    def fake_build_allele(_dp, refseq_accession, _start, _end, **kwargs):
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

    def fake_build_allele(_dp, refseq_accession, _start, _end, **kwargs):
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


def test_project_genomic_variant_applies_cdna_coding_start_site_before_build(mocker):
    captured_build_kwargs = []

    def fake_projection(*args, **kwargs):
        return None

    result = SimpleNamespace(
        cdna=SimpleNamespace(
            refseq="NM_001184880.2",
            pos=(-1143, -1112),
            coding_start_site=2000,
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

    def fake_build_allele(_dp, refseq_accession, start, end, **kwargs):
        captured_build_kwargs.append(
            {
                "refseq_accession": refseq_accession,
                "start": start,
                "end": end,
                **kwargs,
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
        }
    ]
    store_mock.assert_called_once()
