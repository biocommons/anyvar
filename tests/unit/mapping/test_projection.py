"""Unit tests for projection internals."""

# ruff: noqa: SLF001

from types import SimpleNamespace
from unittest.mock import call

import pytest
from cool_seq_tool.schemas import Strand
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


class ProteinProjectionDataProxy(FakeDataProxy):
    """Fake transcript/protein sequence store for protein projection tests."""

    def __init__(
        self,
        transcript_sequence: str = "ATG",
        protein_sequence: str = "M",
        refget_failures: set[str] | None = None,
        sequence_failures: set[str] | None = None,
    ):
        super().__init__()
        self.transcript_sequence = transcript_sequence
        self.protein_sequence = protein_sequence
        self.refget_failures = refget_failures or set()
        self.sequence_failures = sequence_failures or set()

    def translate_sequence_identifier(
        self, accession: str, target_namespace: str
    ) -> list[str]:
        if target_namespace != "ga4gh":
            msg = f"unexpected namespace: {target_namespace}"
            raise AssertionError(msg)
        if accession in self.refget_failures:
            raise KeyError(accession)
        if accession.startswith("NM_"):
            return ["ga4gh:SQ.transcript"]
        if accession.startswith("NP_"):
            return ["ga4gh:SQ.protein"]
        return super().translate_sequence_identifier(accession, target_namespace)

    def get_sequence(self, identifier: str, start: int, end: int) -> str:
        self.sequence_calls.append((identifier, start, end))
        if identifier in self.sequence_failures:
            raise KeyError(identifier)
        if identifier == "ga4gh:SQ.transcript":
            return self.transcript_sequence
        if identifier == "ga4gh:SQ.protein":
            return self.protein_sequence
        return super().get_sequence(identifier, start, end)


class FakeFuture:
    def __init__(self, result):
        self._result = result

    def result(self, timeout: int):
        _ = timeout
        return self._result


class TimeoutFuture:
    def __init__(self):
        self.cancelled = False
        self.timeout: int | None = None

    def result(self, timeout: int):
        self.timeout = timeout
        raise projection.concurrent.futures.TimeoutError

    def cancel(self):
        self.cancelled = True
        return True


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


def test_project_genomic_state_to_cdna_literal_reverse_complements_negative_strand_literal_state():
    dp = FakeDataProxy()
    variation = SimpleNamespace(
        id="ga4gh:VA.input",
        state=models.LiteralSequenceExpression(
            type="LiteralSequenceExpression",
            sequence="A",
        ),
    )
    cdna = SimpleNamespace(strand=SimpleNamespace(value=-1))

    state = projection._project_genomic_state_to_cdna_literal(dp, variation, cdna)

    assert state == models.LiteralSequenceExpression(
        type="LiteralSequenceExpression",
        sequence="T",
    )


def test_project_genomic_state_to_cdna_literal_expands_positive_strand_reference_length_state():
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

    state = projection._project_genomic_state_to_cdna_literal(dp, variation, cdna)

    assert state == models.LiteralSequenceExpression(
        type="LiteralSequenceExpression",
        sequence="CTC",
    )


def test_project_genomic_state_to_cdna_literal_reverse_complements_negative_strand_rle_sequence():
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

    state = projection._project_genomic_state_to_cdna_literal(dp, variation, cdna)

    assert state == models.LiteralSequenceExpression(
        type="LiteralSequenceExpression",
        sequence="GAG",
    )


def test_project_genomic_state_to_cdna_literal_expands_rle_without_embedded_sequence(
    mocker,
):
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

    state = projection._project_genomic_state_to_cdna_literal(dp, variation, cdna)

    dp.get_sequence.assert_called_once_with("ga4gh:SQ.genomic", start=10, end=15)
    denormalize_mock.assert_called_once_with("CTCTC", 2, 3)
    assert state == models.LiteralSequenceExpression(
        type="LiteralSequenceExpression",
        sequence="CTC",
    )


def test_project_genomic_state_to_cdna_literal_raises_projection_error_when_helper_fails(
    mocker,
):
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
        projection._project_genomic_state_to_cdna_literal(dp, variation, cdna)


def test_derive_protein_substitution_state_uses_bioutils_translate_cds(mocker):
    dp = ProteinProjectionDataProxy(transcript_sequence="ATG", protein_sequence="M")
    translate_cds = mocker.patch.object(
        projection.bioutils_sequences,
        "translate_cds",
        side_effect=["M", "L"],
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

    assert translate_cds.mock_calls == [
        call(
            "ATG",
            full_codons=True,
            ter_symbol="*",
            translation_table=projection.TranslationTable.standard,
        ),
        call(
            "TTG",
            full_codons=True,
            ter_symbol="*",
            translation_table=projection.TranslationTable.standard,
        ),
    ]
    assert state == models.LiteralSequenceExpression(
        type="LiteralSequenceExpression",
        sequence="L",
    )


def test_select_translation_table_for_codon_returns_standard_for_reference_match():
    dp = ProteinProjectionDataProxy(transcript_sequence="ATG", protein_sequence="M")
    protein = SimpleNamespace(refseq="NP_004324.2", pos=(0, 1))

    table = projection._select_translation_table_for_codon(dp, protein, "ATG")

    assert table == projection.TranslationTable.standard
    assert dp.sequence_calls == [("ga4gh:SQ.protein", 0, 1)]


def test_select_translation_table_for_codon_raises_for_standard_mismatch():
    dp = ProteinProjectionDataProxy(transcript_sequence="ATG", protein_sequence="L")
    protein = SimpleNamespace(refseq="NP_004324.2", pos=(0, 1))

    with pytest.raises(projection.ProjectionError):
        projection._select_translation_table_for_codon(dp, protein, "ATG")


def test_select_translation_table_for_codon_returns_selenocysteine_for_tga_to_u():
    dp = ProteinProjectionDataProxy(transcript_sequence="TGA", protein_sequence="U")
    protein = SimpleNamespace(refseq="NP_004324.2", pos=(0, 1))

    table = projection._select_translation_table_for_codon(dp, protein, "TGA")

    assert table == projection.TranslationTable.selenocysteine


def test_select_translation_table_for_codon_rejects_non_tga_to_u():
    dp = ProteinProjectionDataProxy(transcript_sequence="ATG", protein_sequence="U")
    protein = SimpleNamespace(refseq="NP_004324.2", pos=(0, 1))

    with pytest.raises(projection.ProjectionError):
        projection._select_translation_table_for_codon(dp, protein, "ATG")


def test_select_translation_table_for_codon_rejects_tga_to_non_u_mismatch():
    dp = ProteinProjectionDataProxy(transcript_sequence="TGA", protein_sequence="W")
    protein = SimpleNamespace(refseq="NP_004324.2", pos=(0, 1))

    with pytest.raises(projection.ProjectionError):
        projection._select_translation_table_for_codon(dp, protein, "TGA")


def test_select_translation_table_for_codon_raises_when_protein_refget_fails():
    dp = ProteinProjectionDataProxy(refget_failures={"NP_004324.2"})
    protein = SimpleNamespace(refseq="NP_004324.2", pos=(0, 1))

    with pytest.raises(projection.ProjectionError):
        projection._select_translation_table_for_codon(dp, protein, "ATG")


def test_select_translation_table_for_codon_raises_when_protein_fetch_fails():
    dp = ProteinProjectionDataProxy(sequence_failures={"ga4gh:SQ.protein"})
    protein = SimpleNamespace(refseq="NP_004324.2", pos=(0, 1))

    with pytest.raises(projection.ProjectionError):
        projection._select_translation_table_for_codon(dp, protein, "ATG")


def test_select_translation_table_for_codon_rejects_ambiguous_reference_translation():
    dp = ProteinProjectionDataProxy(transcript_sequence="NNN", protein_sequence="M")
    protein = SimpleNamespace(refseq="NP_004324.2", pos=(0, 1))

    with pytest.raises(projection.ProjectionError):
        projection._select_translation_table_for_codon(dp, protein, "NNN")


def test_select_translation_table_for_codon_rejects_malformed_reference_codon():
    dp = ProteinProjectionDataProxy(transcript_sequence="AT", protein_sequence="M")
    protein = SimpleNamespace(refseq="NP_004324.2", pos=(0, 1))

    with pytest.raises(projection.ProjectionError):
        projection._select_translation_table_for_codon(dp, protein, "AT")


def test_derive_protein_substitution_state_allows_validated_stop_gain():
    dp = ProteinProjectionDataProxy(transcript_sequence="TGG", protein_sequence="W")
    cdna = SimpleNamespace(refseq="NM_004333.6", coding_start_site=200)
    protein = SimpleNamespace(refseq="NP_004324.2", pos=(0, 1))
    cdna_state = models.LiteralSequenceExpression(
        type="LiteralSequenceExpression",
        sequence="A",
    )

    state = projection._derive_protein_substitution_state(
        dp,
        cdna,
        protein,
        202,
        203,
        cdna_state,
    )

    assert state == models.LiteralSequenceExpression(
        type="LiteralSequenceExpression",
        sequence="*",
    )


def test_derive_protein_substitution_state_allows_validated_selenocysteine():
    dp = ProteinProjectionDataProxy(transcript_sequence="TGA", protein_sequence="U")
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

    assert state == models.LiteralSequenceExpression(
        type="LiteralSequenceExpression",
        sequence="U",
    )


def test_derive_protein_substitution_state_rejects_ambiguous_alt_translation():
    dp = ProteinProjectionDataProxy(transcript_sequence="ATG", protein_sequence="M")
    cdna = SimpleNamespace(refseq="NM_004333.6", coding_start_site=200)
    protein = SimpleNamespace(refseq="NP_004324.2", pos=(0, 1))
    cdna_state = models.LiteralSequenceExpression(
        type="LiteralSequenceExpression",
        sequence="N",
    )

    with pytest.raises(projection.ProjectionError):
        projection._derive_protein_substitution_state(
            dp,
            cdna,
            protein,
            202,
            203,
            cdna_state,
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


def test_variant_projector_close_stops_loop_thread():
    projector = projection.VariantProjector(cst=SimpleNamespace(), dp=object())

    assert projector._thread.is_alive()
    assert not projector._loop.is_closed()

    projector.close()

    assert not projector._thread.is_alive()
    assert projector._loop.is_closed()

    projector.close()


def test_add_mappings_dispatches_genomic_accession(mocker):
    projector = object.__new__(projection.VariantProjector)
    projector.dp = object()
    project_genomic = mocker.patch.object(
        projector,
        "_project_genomic_variant",
        return_value=["genomic"],
    )
    project_transcript = mocker.patch.object(projector, "_project_transcript_variant")
    mocker.patch.object(
        projection,
        "_get_refseq_accession",
        return_value="NC_000007.14",
    )
    variation = SimpleNamespace(
        id="ga4gh:VA.input",
        location=SimpleNamespace(
            sequenceReference=SimpleNamespace(refgetAccession="SQ.genomic")
        ),
    )
    storage = mocker.Mock()

    messages = projector.add_mappings(variation, storage)

    assert messages == ["genomic"]
    project_genomic.assert_called_once_with(variation, storage, "NC_000007.14")
    project_transcript.assert_not_called()


def test_add_mappings_dispatches_transcript_accession(mocker):
    projector = object.__new__(projection.VariantProjector)
    projector.dp = object()
    project_genomic = mocker.patch.object(projector, "_project_genomic_variant")
    project_transcript = mocker.patch.object(
        projector,
        "_project_transcript_variant",
        return_value=["transcript"],
    )
    mocker.patch.object(
        projection,
        "_get_refseq_accession",
        return_value="NM_004333.6",
    )
    variation = SimpleNamespace(
        id="ga4gh:VA.input",
        location=SimpleNamespace(
            sequenceReference=SimpleNamespace(refgetAccession="SQ.transcript")
        ),
    )
    storage = mocker.Mock()

    messages = projector.add_mappings(variation, storage)

    assert messages == ["transcript"]
    project_genomic.assert_not_called()
    project_transcript.assert_called_once_with(variation, storage, "NM_004333.6")


def test_resolve_transcript_to_protein_metadata_skips_without_cds_metadata():
    class FakeUtaDb:
        async def get_cds_start_end(self, transcript_ac):
            _ = transcript_ac

    projector = object.__new__(projection.VariantProjector)
    projector.cst = SimpleNamespace(mane_transcript=SimpleNamespace(uta_db=FakeUtaDb()))

    result = projection.asyncio.run(
        projector._resolve_transcript_to_protein_metadata("NR_000001.1", 10, 11)
    )

    assert result == projection._TranscriptToProteinMetadata(
        cdna=None,
        message="Projection skipped: no CDS metadata for transcript NR_000001.1",
    )


def test_resolve_transcript_to_protein_metadata_skips_utr_without_alignment_lookup():
    class FakeUtaDb:
        async def get_cds_start_end(self, transcript_ac):
            _ = transcript_ac
            return 200, 2200

        async def get_genomic_tx_data(self, *args, **kwargs):
            _ = args, kwargs
            msg = "UTR variants should not need transcript alignment metadata"
            raise AssertionError(msg)

        async def get_transcripts(self, *args, **kwargs):
            _ = args, kwargs
            msg = "UTR variants should not need protein metadata"
            raise AssertionError(msg)

    projector = object.__new__(projection.VariantProjector)
    projector.cst = SimpleNamespace(mane_transcript=SimpleNamespace(uta_db=FakeUtaDb()))

    result = projection.asyncio.run(
        projector._resolve_transcript_to_protein_metadata("NM_001184880.2", 10, 11)
    )

    assert result == projection._TranscriptToProteinMetadata(
        cdna=projection._TranscriptProjection(
            refseq="NM_001184880.2",
            pos=(-190, -189),
            coding_start_site=200,
            coding_end_site=2200,
        )
    )


def test_resolve_transcript_to_protein_metadata_resolves_exact_protein_accession():
    class FakeTranscripts:
        def __init__(self, rows):
            self.rows = rows

        def is_empty(self):
            return not self.rows

        def iter_rows(self, named=False):
            assert named is True
            return iter(self.rows)

    class FakeUtaDb:
        def __init__(self):
            self.genomic_tx_data_calls = []
            self.get_transcripts_calls = []

        async def get_cds_start_end(self, transcript_ac):
            _ = transcript_ac
            return 200, 2200

        async def get_genomic_tx_data(self, tx_ac, pos, annotation_layer):
            self.genomic_tx_data_calls.append((tx_ac, pos, annotation_layer))
            return SimpleNamespace(
                gene="BRAF",
                alt_ac="NC_000007.14",
                strand=Strand.NEGATIVE,
            )

        async def get_transcripts(
            self,
            start_pos,
            end_pos,
            gene,
            use_tx_pos,
            alt_ac,
        ):
            self.get_transcripts_calls.append(
                {
                    "start_pos": start_pos,
                    "end_pos": end_pos,
                    "gene": gene,
                    "use_tx_pos": use_tx_pos,
                    "alt_ac": alt_ac,
                }
            )
            return FakeTranscripts(
                [
                    {"tx_ac": "NM_other.1", "pro_ac": "NP_other.1"},
                    {"tx_ac": "NM_004333.6", "pro_ac": "NP_004324.2"},
                ]
            )

    uta_db = FakeUtaDb()
    projector = object.__new__(projection.VariantProjector)
    projector.cst = SimpleNamespace(mane_transcript=SimpleNamespace(uta_db=uta_db))

    result = projection.asyncio.run(
        projector._resolve_transcript_to_protein_metadata("NM_004333.6", 300, 301)
    )

    assert result.message is None
    assert result.cdna.refseq == "NM_004333.6"
    assert result.cdna.pos == (100, 101)
    assert result.cdna.strand == Strand.NEGATIVE
    assert result.cdna.coding_start_site == 200
    assert result.cdna.coding_end_site == 2200
    assert result.protein == projection._ProteinProjection(
        refseq="NP_004324.2",
        pos=(33, 34),
    )
    assert uta_db.genomic_tx_data_calls == [
        ("NM_004333.6", (300, 301), projection.AnnotationLayer.CDNA)
    ]
    assert uta_db.get_transcripts_calls == [
        {
            "start_pos": 100,
            "end_pos": 101,
            "gene": "BRAF",
            "use_tx_pos": True,
            "alt_ac": "NC_000007.14",
        }
    ]


def test_project_transcript_variant_creates_translate_mapping(mocker):
    cdna = SimpleNamespace(
        refseq="NM_004333.6",
        pos=(100, 101),
        coding_start_site=200,
        coding_end_site=2200,
    )
    protein = SimpleNamespace(refseq="NP_004324.2", pos=(33, 34))
    result = projection._TranscriptToProteinMetadata(cdna=cdna, protein=protein)

    projector = object.__new__(projection.VariantProjector)
    projector.dp = object()
    mocker.patch.object(
        projector,
        "_resolve_transcript_to_protein_metadata",
        new=mocker.Mock(return_value=result),
    )
    mocker.patch.object(projector, "_run_async_projection", return_value=(result, None))
    mocker.patch.object(
        projection,
        "_derive_protein_substitution_state",
        return_value=models.LiteralSequenceExpression(
            type="LiteralSequenceExpression",
            sequence="L",
        ),
    )

    build_calls = []

    def fake_build_allele(_dp, refseq_accession, _start, _end, _state):
        build_calls.append(refseq_accession)
        return SimpleNamespace(id=f"ga4gh:VA.{refseq_accession}")

    mocker.patch.object(projection, "_build_allele", side_effect=fake_build_allele)
    store_mock = mocker.patch.object(projection, "_store_projected_variant")
    variation = SimpleNamespace(
        id="ga4gh:VA.input",
        state=models.LiteralSequenceExpression(
            type="LiteralSequenceExpression",
            sequence="A",
        ),
        location=SimpleNamespace(start=300, end=301),
    )

    messages = projector._project_transcript_variant(
        variation, mocker.Mock(), "NM_004333.6"
    )

    assert messages is None
    assert build_calls == ["NP_004324.2"]
    store_mock.assert_called_once()
    assert store_mock.call_args.args[1] == "ga4gh:VA.input"
    assert store_mock.call_args.args[3] == projection.VariationMappingType.TRANSLATE_TO


def test_project_transcript_variant_skips_missing_metadata_before_state_derivation(
    mocker,
):
    result = projection._TranscriptToProteinMetadata(
        cdna=None,
        message="Projection skipped: no CDS metadata for transcript NR_000001.1",
    )
    projector = object.__new__(projection.VariantProjector)
    projector.dp = object()
    mocker.patch.object(
        projector,
        "_resolve_transcript_to_protein_metadata",
        new=mocker.Mock(return_value=result),
    )
    mocker.patch.object(projector, "_run_async_projection", return_value=(result, None))
    state_mock = mocker.patch.object(projection, "_get_transcript_literal_state")
    variation = SimpleNamespace(
        id="ga4gh:VA.input",
        state=SimpleNamespace(type="UnsupportedState"),
        location=SimpleNamespace(start=10, end=11),
    )

    messages = projector._project_transcript_variant(
        variation, mocker.Mock(), "NR_000001.1"
    )

    assert messages == [
        "Projection skipped: no CDS metadata for transcript NR_000001.1"
    ]
    state_mock.assert_not_called()


def test_project_transcript_variant_skips_missing_protein_before_state_derivation(
    mocker,
):
    cdna = SimpleNamespace(
        refseq="NM_004333.6",
        pos=(100, 101),
        coding_start_site=200,
        coding_end_site=2200,
    )
    result = projection._TranscriptToProteinMetadata(cdna=cdna, protein=None)
    projector = object.__new__(projection.VariantProjector)
    projector.dp = object()
    mocker.patch.object(
        projector,
        "_resolve_transcript_to_protein_metadata",
        new=mocker.Mock(return_value=result),
    )
    mocker.patch.object(projector, "_run_async_projection", return_value=(result, None))
    state_mock = mocker.patch.object(projection, "_get_transcript_literal_state")
    variation = SimpleNamespace(
        id="ga4gh:VA.input",
        state=SimpleNamespace(type="UnsupportedState"),
        location=SimpleNamespace(start=300, end=301),
    )

    messages = projector._project_transcript_variant(
        variation, mocker.Mock(), "NM_004333.6"
    )

    assert messages == [
        "Projection skipped: no associated protein accession for transcript NM_004333.6"
    ]
    state_mock.assert_not_called()


def test_project_transcript_variant_skips_utr_without_protein_mapping(mocker):
    cdna = SimpleNamespace(
        refseq="NM_001184880.2",
        pos=(-1143, -1112),
        coding_start_site=2000,
        coding_end_site=4000,
    )
    result = projection._TranscriptToProteinMetadata(cdna=cdna, protein=None)

    projector = object.__new__(projection.VariantProjector)
    projector.dp = object()
    mocker.patch.object(
        projector,
        "_resolve_transcript_to_protein_metadata",
        new=mocker.Mock(return_value=result),
    )
    mocker.patch.object(projector, "_run_async_projection", return_value=(result, None))
    store_mock = mocker.patch.object(projection, "_store_projected_variant")
    build_mock = mocker.patch.object(projection, "_build_allele")
    variation = SimpleNamespace(
        id="ga4gh:VA.input",
        state=models.LiteralSequenceExpression(
            type="LiteralSequenceExpression",
            sequence="T",
        ),
        location=SimpleNamespace(start=857, end=888),
    )

    messages = projector._project_transcript_variant(
        variation, mocker.Mock(), "NM_001184880.2"
    )

    assert messages is None
    build_mock.assert_not_called()
    store_mock.assert_not_called()


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


def test_project_genomic_variant_uses_shared_transcript_to_protein_helper(mocker):
    """Genomic projection stores cDNA then delegates cDNA->protein."""
    cdna = SimpleNamespace(
        refseq="NM_004333.6",
        pos=(100, 101),
        coding_start_site=200,
        coding_end_site=2200,
    )
    protein = SimpleNamespace(refseq="NP_004324.2", pos=(33, 34))
    result = SimpleNamespace(cdna=cdna, protein=protein)

    mocker.patch.object(
        projection, "_get_refseq_accession", return_value="NC_000007.14"
    )
    mocker.patch.object(
        projection.asyncio,
        "run_coroutine_threadsafe",
        return_value=FakeFuture(result),
    )
    mocker.patch.object(
        projection,
        "_build_allele",
        return_value=SimpleNamespace(id="ga4gh:VA.cdna"),
    )
    store_mock = mocker.patch.object(projection, "_store_projected_variant")

    projector = object.__new__(projection.VariantProjector)
    projector.cst = SimpleNamespace(
        mane_transcript=SimpleNamespace(grch38_to_mane_c_p=lambda **kw: None)
    )
    projector.dp = object()
    projector._loop = object()
    protein_helper = mocker.patch.object(
        projector, "_project_transcript_to_protein", return_value=None
    )
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
    storage = mocker.Mock()

    messages = projector._project_genomic_variant(variation, storage)

    assert messages is None
    store_mock.assert_called_once()
    protein_helper.assert_called_once()
    assert protein_helper.call_args.args[:6] == (
        storage,
        "ga4gh:VA.cdna",
        cdna,
        protein,
        300,
        301,
    )
    assert protein_helper.call_args.args[6]() == models.LiteralSequenceExpression(
        type="LiteralSequenceExpression",
        sequence="A",
    )


def test_project_genomic_variant_requests_longest_compatible_fallback(mocker):
    """Genomic projection opts into cool-seq-tool transcript fallback."""
    projection_kwargs = {}

    def fake_grch38_to_mane_c_p(**kwargs):
        projection_kwargs.update(kwargs)
        return object()

    mocker.patch.object(
        projection.asyncio,
        "run_coroutine_threadsafe",
        return_value=FakeFuture(None),
    )

    projector = object.__new__(projection.VariantProjector)
    projector.cst = SimpleNamespace(
        mane_transcript=SimpleNamespace(grch38_to_mane_c_p=fake_grch38_to_mane_c_p)
    )
    projector.dp = object()
    projector._loop = object()
    variation = SimpleNamespace(
        id="ga4gh:VA.input",
        location=SimpleNamespace(
            sequenceReference=SimpleNamespace(refgetAccession="SQ.genomic"),
            start=10117252,
            end=10117253,
        ),
    )

    messages = projector._project_genomic_variant(
        variation, mocker.Mock(), "NC_000023.11"
    )

    assert messages is None
    assert projection_kwargs == {
        "alt_ac": "NC_000023.11",
        "start_pos": 10117252,
        "end_pos": 10117253,
        "coordinate_type": projection.CoordinateType.INTER_RESIDUE,
        "try_longest_compatible": True,
    }


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
    projector.dp = object()
    mocker.patch.object(
        projection,
        "_get_refseq_accession",
        return_value="NC_000007.14",
    )
    mocker.patch.object(
        projector,
        "_project_genomic_variant",
        side_effect=projection.ProjectionError("Projection failed: expected failure"),
    )
    variation = SimpleNamespace(
        id="ga4gh:VA.input",
        location=SimpleNamespace(
            sequenceReference=SimpleNamespace(refgetAccession="SQ.genomic")
        ),
    )

    messages = projector.add_mappings(variation, mocker.Mock())

    assert messages == ["Projection failed: expected failure"]


def test_project_genomic_variant_cancels_timed_out_projection(mocker):
    """Timed-out cool-seq-tool work is cancelled and reported as a timeout."""
    mocker.patch.object(
        projection,
        "_get_refseq_accession",
        return_value="NC_000007.14",
    )
    future = TimeoutFuture()
    # Return a fake scheduled future so no event loop or background thread is needed.
    mocker.patch.object(
        projection.asyncio,
        "run_coroutine_threadsafe",
        return_value=future,
    )

    # Bypass __init__ to avoid starting VariantProjector's real event-loop thread.
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

    assert messages == ["Projection failed: coordinate mapping timed out"]
    assert future.timeout == 30
    assert future.cancelled is True


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
