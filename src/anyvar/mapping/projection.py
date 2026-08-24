"""Project variants across the central dogma: genomic (g.) ↔ coding (c.) ↔ protein (p.)

Uses cool-seq-tool to resolve MANE transcripts with longest-compatible
transcript fallback and map coordinates between molecule types. Follows the
same pattern as liftover.py for storing projected variants and their mappings.
"""

import asyncio
import concurrent.futures
import logging
import math
import threading
from collections.abc import Coroutine
from dataclasses import dataclass
from typing import Any, Protocol

from bioutils import sequences as bioutils_sequences
from bioutils.sequences import TranslationTable
from cool_seq_tool import CoolSeqTool
from cool_seq_tool.mappers.mane_transcript import CdnaRepresentation
from cool_seq_tool.schemas import (
    AnnotationLayer,
    CoordinateType,
    TranscriptPriority,
)
from ga4gh.core import ga4gh_identify
from ga4gh.vrs import models, normalize
from ga4gh.vrs.dataproxy import _DataProxy
from ga4gh.vrs.normalize import denormalize_reference_length_expression

from anyvar.core.categorical_variants import get_molecule_type
from anyvar.core.metadata import VariationMapping, VariationMappingType
from anyvar.core.objects import SupportedVrsVariation
from anyvar.mapping.projection_models import (
    ProjectedVariation,
    ProjectionError,
    ProjectionFailure,
    ProjectionNotApplicable,
    ProjectionOutcome,
    ProjectionResults,
)

_logger = logging.getLogger(__name__)

_CODON_LENGTH = 3
_ASYNC_TIMEOUT = 30


class _RefSeqPositionLike(Protocol):
    """Object shape containing a RefSeq accession and inter-residue coordinates."""

    refseq: str | None
    pos: tuple[int, int]


class _CdnaPositionLike(Protocol):
    """Object shape containing cDNA coordinates relative to a CDS."""

    refseq: str | None
    pos: tuple[int, int]
    coding_start_site: int
    coding_end_site: int


@dataclass(frozen=True)
class _ProteinProjection:
    """Minimal protein representation for direct transcript projection."""

    refseq: str | None
    pos: tuple[int, int]


@dataclass(frozen=True)
class _TranscriptProjection:
    """Minimal transcript representation for protein projection guard checks."""

    refseq: str | None
    pos: tuple[int, int]
    coding_start_site: int
    coding_end_site: int


@dataclass(frozen=True)
class _ProjectionLocation:
    """Validated inter-residue variation coordinates."""

    start: int
    end: int
    refget_accession: str | None = None


def _get_variation_location(
    variation: SupportedVrsVariation,
    *,
    require_refget: bool = False,
) -> _ProjectionLocation:
    """Return validated inter-residue coordinates for a VRS variation."""
    try:
        start = variation.location.start
        end = variation.location.end
        refget_accession = (
            variation.location.sequenceReference.refgetAccession
            if require_refget
            else None
        )
    except AttributeError:
        msg = "Projection unsupported: variant lacks sequence location details"
        raise ProjectionError(msg) from None

    if not isinstance(start, int) or not isinstance(end, int):
        msg = "Projection unsupported for variants with Range positions"
        raise ProjectionError(msg)

    if require_refget and refget_accession is None:
        msg = "Projection unsupported: variant lacks sequence location details"
        raise ProjectionError(msg)

    return _ProjectionLocation(start, end, refget_accession)


def _get_refseq_accession(
    dp: _DataProxy, variation: SupportedVrsVariation
) -> str | None:
    """Retrieve refseq accession for the given variant"""
    location = _get_variation_location(variation, require_refget=True)
    ga4gh_id = f"ga4gh:{location.refget_accession}"
    try:
        aliases = dp.translate_sequence_identifier(ga4gh_id, "refseq")
    except KeyError:
        _logger.debug("No RefSeq alias found for %s", location.refget_accession)
        return None
    if not aliases:
        return None
    # Prefer genomic, then transcript, then protein accessions.
    for prefix in (
        "refseq:NC_",
        "refseq:NM_",
        "refseq:NR_",
        "refseq:XM_",
        "refseq:XR_",
        "refseq:NP_",
        "refseq:XP_",
    ):
        for alias in aliases:
            if alias.startswith(prefix):
                return alias.removeprefix("refseq:")
    # Fall back to first alias
    return aliases[0].removeprefix("refseq:")


def _refseq_to_refget_accession(dp: _DataProxy, refseq_accession: str) -> str:
    """Resolve a RefSeq accession (NC_/NM_/NP_) to a refget accession.

    :param dp: SeqRepo DataProxy instance
    :param refseq_accession: RefSeq accession (e.g. "NM_004333.6")
    :return: refget accession (without ga4gh: prefix)
    :raises ProjectionError: if no refget accession can be resolved
    """
    try:
        refget_accession = dp.derive_refget_accession(refseq_accession)
    except (KeyError, ValueError) as exc:
        msg = f"Could not resolve refget accession for {refseq_accession}"
        raise ProjectionError(msg) from exc
    if not refget_accession:
        msg = f"Could not resolve refget accession for {refseq_accession}"
        raise ProjectionError(msg)
    return refget_accession


def _build_allele(
    dp: _DataProxy,
    refseq_accession: str,
    start: int,
    end: int,
    state: models.LiteralSequenceExpression,
) -> models.Allele:
    """Construct and normalize a VRS Allele.

    :param dp: SeqRepo DataProxy instance
    :param refseq_accession: RefSeq accession (e.g. "NM_004333.6")
    :param start: inter-residue start position
    :param end: inter-residue end position
    :param state: literal projected replacement state
    :return: normalized VRS Allele with computed GA4GH ID
    :raises ProjectionError: if the allele cannot be constructed
    """
    refget_accession = _refseq_to_refget_accession(dp, refseq_accession)

    if start < 0 or end < 0:
        msg = (
            "Could not build allele with negative coordinates for "
            f"{refseq_accession}:{start}-{end}"
        )
        raise ProjectionError(msg)

    seq_ref = models.SequenceReference(
        type="SequenceReference",
        refgetAccession=refget_accession,
    )
    location = models.SequenceLocation(
        type="SequenceLocation",
        sequenceReference=seq_ref,
        start=start,
        end=end,
    )
    # Identify child locations explicitly; allele IDs do not fill nested IDs.
    ga4gh_identify(location, in_place="always")

    allele = models.Allele(
        type="Allele",
        location=location,
        state=state,
    )
    normalized_allele = normalize(allele, data_proxy=dp)
    # Normalization can change location/state, so identify the final objects.
    ga4gh_identify(normalized_allele.location, in_place="always")
    ga4gh_identify(normalized_allele, in_place="always")
    return normalized_allele


def _is_negative_strand(representation: object) -> bool:
    """Return whether a cool-seq-tool representation maps to the negative strand."""
    strand = getattr(representation, "strand", None)
    return getattr(strand, "value", strand) == -1


def _sequence_to_str(sequence: object) -> str:
    """Return string value from plain strings or VRS constrained string root models."""
    return str(getattr(sequence, "root", sequence))


def _reverse_complement(sequence: str) -> str:
    """Return the reverse-complement of a nucleotide sequence."""
    try:
        projected_sequence = bioutils_sequences.reverse_complement(sequence)
    except Exception as exc:
        msg = f"Could not reverse-complement projected sequence {sequence!r}"
        raise ProjectionError(msg) from exc
    if not isinstance(projected_sequence, str):
        msg = f"Could not reverse-complement projected sequence {sequence!r}"
        raise ProjectionError(msg)
    return projected_sequence.upper()


def _project_literal_sequence_state(
    sequence: str, representation: object
) -> models.LiteralSequenceExpression:
    """Project a literal nucleotide state into transcript orientation."""
    if _is_negative_strand(representation):
        sequence = _reverse_complement(sequence)
    try:
        return models.LiteralSequenceExpression(
            type="LiteralSequenceExpression",
            sequence=models.sequenceString(sequence),
        )
    except Exception as exc:
        msg = f"Could not build projected literal sequence state from {sequence!r}"
        raise ProjectionError(msg) from exc


def _reference_length_state_to_literal_sequence(
    dp: _DataProxy,
    variation: SupportedVrsVariation,
    state: models.ReferenceLengthExpression,
) -> str:
    """Return a literal alternate sequence for a source RLE state."""
    state_sequence = getattr(state, "sequence", None)
    if state_sequence is not None:
        return _sequence_to_str(state_sequence)

    # If RLE has no sequence, expand it from the source reference span.
    # This code is only reachable for RLE states, which have int start/end, not Range
    ref_sequence = dp.get_sequence(
        f"ga4gh:{variation.location.sequenceReference.refgetAccession}",
        start=variation.location.start,
        end=variation.location.end,
    )
    return denormalize_reference_length_expression(
        ref_sequence,
        state.repeatSubunitLength,
        state.length,
    )


def _project_genomic_state_to_cdna_literal(
    dp: _DataProxy,
    variation: SupportedVrsVariation,
    cdna: CdnaRepresentation,
) -> models.LiteralSequenceExpression:
    """Derive projected cDNA literal state from the source genomic allele state.

    cool-seq-tool returns projected coordinates, not replacement sequence. VRS
    Allele state must be the alternate state, so projection first derives a
    target literal sequence. Later normalization decides whether the
    final Allele should remain LSE or compact to RLE.
    """
    state = getattr(variation, "state", None)

    if isinstance(state, models.LiteralSequenceExpression):
        state_sequence = getattr(state, "sequence", None)
        if state_sequence is None:
            msg = f"Cannot project cDNA state for {variation.id} without sequence"
            raise ProjectionError(msg)
        sequence = _sequence_to_str(state_sequence)
        return _project_literal_sequence_state(sequence, cdna)

    if isinstance(state, models.ReferenceLengthExpression):
        try:
            sequence = _reference_length_state_to_literal_sequence(dp, variation, state)
        except Exception as exc:
            msg = f"Cannot project cDNA state for {variation.id} from RLE state"
            raise ProjectionError(msg) from exc
        return _project_literal_sequence_state(sequence, cdna)

    msg = (
        f"Cannot project cDNA state for {variation.id} from unsupported state type "
        f"{getattr(state, 'type', type(state).__name__)}"
    )
    raise ProjectionError(msg)


def _get_transcript_literal_state(
    dp: _DataProxy,
    variation: SupportedVrsVariation,
) -> models.LiteralSequenceExpression:
    """Return input transcript state as a literal sequence without strand changes."""
    state = getattr(variation, "state", None)

    if isinstance(state, models.LiteralSequenceExpression):
        state_sequence = getattr(state, "sequence", None)
        if state_sequence is None:
            msg = f"Cannot project transcript state for {variation.id} without sequence"
            raise ProjectionError(msg)
        sequence = _sequence_to_str(state_sequence)
    elif isinstance(state, models.ReferenceLengthExpression):
        try:
            sequence = _reference_length_state_to_literal_sequence(dp, variation, state)
        except Exception as exc:
            msg = f"Cannot project transcript state for {variation.id} from RLE state"
            raise ProjectionError(msg) from exc
    else:
        msg = (
            f"Cannot project transcript state for {variation.id} from unsupported "
            f"state type {getattr(state, 'type', type(state).__name__)}"
        )
        raise ProjectionError(msg)

    try:
        return models.LiteralSequenceExpression(
            type="LiteralSequenceExpression",
            sequence=models.sequenceString(sequence),
        )
    except Exception as exc:
        msg = f"Could not build transcript literal sequence state from {sequence!r}"
        raise ProjectionError(msg) from exc


def _protein_projection_error(protein: _RefSeqPositionLike) -> ProjectionError:
    """Build a consistent expected-failure error for protein projection."""
    return ProjectionError(
        "Projection skipped: could not derive alternate protein state for "
        f"{protein.refseq}"
    )


def _is_specific_protein_residue(amino_acid: object) -> bool:
    """Return whether a protein residue is specific enough to project."""
    # "X" represents an unknown/ambiguous amino acid
    return isinstance(amino_acid, str) and len(amino_acid) == 1 and amino_acid != "X"


def _select_translation_table_for_codon(
    dp: _DataProxy,
    protein: _RefSeqPositionLike,
    ref_codon: str,
) -> TranslationTable:
    """Select a translation table only when the reference codon is validated."""
    if not isinstance(ref_codon, str) or len(ref_codon) != _CODON_LENGTH:
        raise _protein_projection_error(protein)
    if not protein.refseq:
        raise _protein_projection_error(protein)

    try:
        refget_accession = _refseq_to_refget_accession(dp, protein.refseq)
    except ProjectionError as exc:
        raise _protein_projection_error(protein) from exc

    try:
        reference_residue = dp.get_sequence(
            f"ga4gh:{refget_accession}",
            start=protein.pos[0],
            end=protein.pos[0] + 1,
        )
    except Exception as exc:
        _logger.exception(
            "Failed to fetch protein residue for %s:%d-%d",
            protein.refseq,
            protein.pos[0],
            protein.pos[0] + 1,
        )
        raise _protein_projection_error(protein) from exc

    if not _is_specific_protein_residue(reference_residue):
        raise _protein_projection_error(protein)

    # Try the standard code first; special tables are only fallback validation.
    try:
        ref_amino_acid = bioutils_sequences.translate_cds(
            ref_codon,
            full_codons=True,
            ter_symbol="*",
            translation_table=TranslationTable.standard,
        )
    except Exception as exc:
        raise _protein_projection_error(protein) from exc

    if not _is_specific_protein_residue(ref_amino_acid):
        raise _protein_projection_error(protein)
    if ref_amino_acid == reference_residue:
        return TranslationTable.standard

    if ref_codon.upper().replace("U", "T") == "TGA" and reference_residue == "U":
        try:
            # Validate the selected table before using it for the alternate codon.
            sec_ref_amino_acid = bioutils_sequences.translate_cds(
                ref_codon,
                full_codons=True,
                ter_symbol="*",
                translation_table=TranslationTable.selenocysteine,
            )
        except Exception as exc:
            raise _protein_projection_error(protein) from exc
        if sec_ref_amino_acid != "U":
            raise _protein_projection_error(protein)
        return TranslationTable.selenocysteine

    raise _protein_projection_error(protein)


def _derive_protein_substitution_state(
    dp: _DataProxy,
    cdna: _CdnaPositionLike,
    protein: _RefSeqPositionLike,
    cdna_start: int,
    cdna_end: int,
    cdna_state: models.LiteralSequenceExpression,
) -> models.LiteralSequenceExpression:
    """Derive protein state for simple single-codon substitutions.

    Frameshifts and indels need richer consequence modeling
    so this raises ``ProjectionError``.
    """
    alt_sequence = _sequence_to_str(cdna_state.sequence)
    if len(alt_sequence) != cdna_end - cdna_start:
        raise _protein_projection_error(protein)
    # Only handle single-nucleotide substitutions
    # which should translate to single amino acid changes.
    # More complicated scenarios (indels, multibase substitutions, frameshifts) not implemented.
    if len(alt_sequence) != 1 or protein.pos[1] - protein.pos[0] != 1:
        raise _protein_projection_error(protein)

    # Simple model: residue i starts at transcript coordinate CDS start + i * 3.
    codon_start = cdna.coding_start_site + (protein.pos[0] * 3)
    codon_end = codon_start + _CODON_LENGTH
    # Reject effects outside this one codon; they need consequence modeling.
    if not codon_start <= cdna_start < cdna_end <= codon_end:
        raise _protein_projection_error(protein)
    if not cdna.refseq:
        raise _protein_projection_error(protein)

    try:
        refget_accession = _refseq_to_refget_accession(dp, cdna.refseq)
    except ProjectionError as exc:
        raise _protein_projection_error(protein) from exc
    try:
        ref_codon = dp.get_sequence(
            f"ga4gh:{refget_accession}", start=codon_start, end=codon_end
        )
    except Exception as exc:
        _logger.exception(
            "Failed to fetch coding codon for %s:%d-%d",
            cdna.refseq,
            codon_start,
            codon_end,
        )
        raise _protein_projection_error(protein) from exc

    translation_table = _select_translation_table_for_codon(dp, protein, ref_codon)
    # Build the alternate codon by replacing the affected slice with cDNA state.
    alt_codon = (
        ref_codon[: cdna_start - codon_start]
        + alt_sequence
        + ref_codon[cdna_end - codon_start :]
    )
    try:
        alt_amino_acid = bioutils_sequences.translate_cds(
            alt_codon,
            full_codons=True,
            ter_symbol="*",
            translation_table=translation_table,
        )
    except Exception as exc:
        raise _protein_projection_error(protein) from exc
    if not _is_specific_protein_residue(alt_amino_acid):
        raise _protein_projection_error(protein)

    try:
        return models.LiteralSequenceExpression(
            type="LiteralSequenceExpression",
            sequence=models.sequenceString(alt_amino_acid),
        )
    except Exception as exc:
        raise _protein_projection_error(protein) from exc


def _is_utr_variant(cdna: _CdnaPositionLike) -> str | None:
    """Check if a cDNA variant extends into a UTR region.

    cdna.pos is CDS-relative (0 = CDS start). The CDS spans positions
    [0, coding_end_site - coding_start_site) in these coordinates. A variant
    is flagged if ANY part extends outside the CDS, including boundary-spanning
    variants.

    :param cdna: CdnaRepresentation with pos, coding_start_site, coding_end_site
    :return: "5_prime" if any part extends into the 5' UTR, "3_prime" if any
        part extends into the 3' UTR, or None if entirely within the CDS
    """
    start, end = cdna.pos
    cds_length = cdna.coding_end_site - cdna.coding_start_site

    if start == end:
        if start <= 0:
            return "5_prime"
        if start >= cds_length:
            return "3_prime"
    elif start < 0:
        return "5_prime"
    elif end > cds_length:
        return "3_prime"
    return None


def _cdna_pos_to_protein_pos(c_pos: tuple[int, int]) -> tuple[int, int]:
    """Get protein inter-residue coordinates from CDS-relative cDNA coordinates."""
    end = math.ceil(c_pos[1] / _CODON_LENGTH)
    if c_pos[1] - c_pos[0] == 1:
        start = end - 1
    else:
        start = math.ceil((c_pos[0] + 1) / _CODON_LENGTH) - 1
    return start, end


def _cdna_pos_to_transcript_pos(cdna: _CdnaPositionLike) -> tuple[int, int]:
    """Get transcript inter-residue coordinates from CDS-relative cDNA coordinates."""
    return (
        cdna.pos[0] + cdna.coding_start_site,
        cdna.pos[1] + cdna.coding_start_site,
    )


class VariantProjector:
    """Projects variants across the central dogma using cool-seq-tool selection.

    Holds references to CoolSeqTool and DataProxy so callers only need to
    provide the variation and storage.

    Uses a dedicated event loop in a background thread for async cool-seq-tool
    calls, since the sync FastAPI endpoints run in a thread pool and can't use
    the main uvicorn event loop.
    """

    def __init__(self, cst: CoolSeqTool, dp: _DataProxy) -> None:
        """Initialize the projector.

        :param cst: CoolSeqTool instance
        :param dp: SeqRepo DataProxy instance
        """
        self.cst = cst
        self.dp = dp
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(
            target=self._loop.run_forever, daemon=True, name="projector-loop"
        )
        self._thread.start()

    def _uta_repository(self):  # noqa: ANN202
        """Return CoolSeqTool's UTA repository context manager."""
        return self.cst.mane_transcript.uta_db.repository()

    def close(self, timeout: float = 5.0) -> None:
        """Stop the projector event loop thread."""
        if self._loop.is_closed():
            return

        if self._thread.is_alive():
            uta_db = getattr(getattr(self.cst, "mane_transcript", None), "uta_db", None)
            close = getattr(uta_db, "close", None)
            if close is not None:
                try:
                    future = asyncio.run_coroutine_threadsafe(close(), self._loop)
                    future.result(timeout=timeout)
                except Exception:  # noqa: BLE001
                    _logger.debug("Failed to close UTA connection pool", exc_info=True)

            self._loop.call_soon_threadsafe(self._loop.stop)
            self._thread.join(timeout=timeout)

            if self._thread.is_alive():
                _logger.warning("Projector event loop thread did not stop cleanly")
                return

        self._loop.close()

    def _run_async_projection(
        self,
        awaitable: Coroutine[Any, Any, object],
        *,
        timeout_message: str,
        failure_message: str,
        log_context: str,
    ) -> object | None:
        """Run a cool-seq-tool async task on the projector event loop."""
        future: concurrent.futures.Future | None = None
        try:
            future = asyncio.run_coroutine_threadsafe(awaitable, self._loop)
            return future.result(timeout=_ASYNC_TIMEOUT)
        except concurrent.futures.TimeoutError:
            if future is not None:
                future.cancel()
            _logger.warning("%s timed out", log_context)
            raise ProjectionError(timeout_message) from None
        except Exception as exc:
            _logger.exception("%s failed", log_context)
            raise ProjectionError(failure_message) from exc

    async def _get_transcript_protein_refseq(
        self,
        transcript_ac: str,
        cdna_pos: tuple[int, int],
        *,
        gene: str | None,
        alt_ac: str | None,
    ) -> str | None:
        """Return the protein accession associated with an exact transcript."""
        async with self._uta_repository() as uta:
            transcripts = await uta.get_transcripts(
                start_pos=cdna_pos[0],
                end_pos=cdna_pos[1],
                gene=gene,
                use_tx_pos=True,
                alt_ac=alt_ac,
            )
        if transcripts is None or transcripts.is_empty():
            return None

        for row in transcripts.iter_rows(named=True):
            if row.get("tx_ac") != transcript_ac:
                continue
            protein_ac = row.get("pro_ac")
            if isinstance(protein_ac, str) and protein_ac:
                return protein_ac
        return None

    async def _resolve_transcript_to_protein_metadata(
        self,
        transcript_ac: str,
        transcript_start: int,
        transcript_end: int,
    ) -> tuple[_CdnaPositionLike, _ProteinProjection | None]:
        """Resolve exact transcript metadata needed for protein projection."""
        async with self._uta_repository() as uta:
            cds_start_end = await uta.get_cds_start_end(transcript_ac)
        if cds_start_end is None:
            msg = f"Projection skipped: no CDS metadata for transcript {transcript_ac}"
            raise ProjectionError(msg)

        coding_start_site, coding_end_site = cds_start_end
        cdna_pos = (
            transcript_start - coding_start_site,
            transcript_end - coding_start_site,
        )
        transcript_projection = _TranscriptProjection(
            refseq=transcript_ac,
            pos=cdna_pos,
            coding_start_site=coding_start_site,
            coding_end_site=coding_end_site,
        )
        if _is_utr_variant(transcript_projection):
            return transcript_projection, None

        async with self._uta_repository() as uta:
            genomic_tx_data = await uta.get_genomic_tx_data(
                transcript_ac,
                (transcript_start, transcript_end),
                annotation_layer=AnnotationLayer.CDNA,
            )
        if genomic_tx_data is None:
            msg = (
                "Projection skipped: no transcript alignment metadata for "
                f"{transcript_ac}"
            )
            raise ProjectionError(msg)

        cdna = CdnaRepresentation(
            refseq=transcript_ac,
            pos=cdna_pos,
            strand=genomic_tx_data.strand,
            status=TranscriptPriority.GRCH38,
            coding_start_site=coding_start_site,
            coding_end_site=coding_end_site,
        )

        protein_ac = await self._get_transcript_protein_refseq(
            transcript_ac,
            cdna_pos,
            gene=genomic_tx_data.gene,
            alt_ac=genomic_tx_data.alt_ac,
        )
        protein = (
            _ProteinProjection(
                refseq=protein_ac,
                pos=_cdna_pos_to_protein_pos(cdna_pos),
            )
            if protein_ac
            else None
        )
        return cdna, protein

    def _project_transcript_to_protein(
        self,
        source_id: str,
        cdna: _CdnaPositionLike,
        protein: _RefSeqPositionLike | None,
        cdna_start: int,
        cdna_end: int,
        cdna_state: models.LiteralSequenceExpression,
        *,
        missing_protein_message: str | None = None,
    ) -> ProjectionOutcome:
        """Project a transcript allele to protein and store the mapping."""
        utr_region = _is_utr_variant(cdna)
        if utr_region:
            msg = f"Skipping protein projection for {cdna.refseq}: variant in {utr_region} UTR"
            _logger.info(msg)
            return ProjectionNotApplicable(source_id, msg, models.MoleculeType.PROTEIN)

        if not protein or not protein.refseq:
            msg = f"No protein representation returned for {cdna.refseq}"
            _logger.debug(msg)
            if missing_protein_message:
                return ProjectionFailure(
                    source_id,
                    missing_protein_message,
                    destination_molecule_type=models.MoleculeType.PROTEIN,
                )
            return ProjectionNotApplicable(source_id, msg, models.MoleculeType.PROTEIN)

        try:
            protein_state = _derive_protein_substitution_state(
                self.dp,
                cdna,
                protein,
                cdna_start,
                cdna_end,
                cdna_state,
            )
        except ProjectionError as e:
            return ProjectionFailure(
                source_id=source_id,
                description=str(e),
                destination_molecule_type=models.MoleculeType.PROTEIN,
            )

        protein_allele = _build_allele(
            self.dp,
            protein.refseq,
            protein.pos[0],
            protein.pos[1],
            protein_state,
        )
        return ProjectedVariation(
            destination_variation=protein_allele,
            mapping=VariationMapping(
                source_id=source_id,
                dest_id=protein_allele.id,
                mapping_type=VariationMappingType.TRANSLATE_TO,
            ),
        )

    def _project_genomic_to_transcript(
        self,
        source_id: str,
        variation: SupportedVrsVariation,
        cdna: CdnaRepresentation,
        genomic_ac: str,
    ) -> ProjectionOutcome:
        """Build and store the transcript allele projected from a genomic variant."""
        if not cdna.refseq:
            msg = f"No RefSeq cDNA accession in projection result for {genomic_ac}"
            _logger.debug(msg)
            return ProjectionNotApplicable(
                source_id=source_id,
                reason=msg,
                destination_molecule_type=models.MoleculeType.RNA,
            )

        cdna_start, cdna_end = _cdna_pos_to_transcript_pos(cdna)
        cdna_state = _project_genomic_state_to_cdna_literal(self.dp, variation, cdna)
        cdna_allele = _build_allele(
            self.dp,
            cdna.refseq,
            cdna_start,
            cdna_end,
            cdna_state,
        )
        return ProjectedVariation(
            destination_variation=cdna_allele,
            mapping=VariationMapping(
                source_id=source_id,
                dest_id=cdna_allele.id,
                mapping_type=VariationMappingType.TRANSCRIBE_TO,
            ),
        )

    async def _resolve_genomic_mane_c_p(
        self,
        genomic_ac: str,
        start: int,
        end: int,
    ) -> object | None:
        """Resolve genomic input to GRCh38 MANE c./p. projection metadata."""
        grch38 = await self.cst.mane_transcript.g_to_grch38(
            ac=genomic_ac,
            start_pos=start,
            end_pos=end,
            get_mane_genes=False,
            coordinate_type=CoordinateType.INTER_RESIDUE,
        )
        if grch38 is None:
            return None

        return await self.cst.mane_transcript.grch38_to_mane_c_p(
            alt_ac=grch38.ac,
            start_pos=grch38.pos[0],
            end_pos=grch38.pos[1],
            coordinate_type=CoordinateType.INTER_RESIDUE,
            try_longest_compatible=True,
        )

    def _project_genomic_variant(
        self,
        variation: SupportedVrsVariation,
        genomic_ac: str,
    ) -> ProjectionResults:
        """Project a genomic variant to coding and protein representations.

        :param variation: genomic VRS variation
        :param storage: Storage instance
        :param genomic_ac: pre-resolved genomic RefSeq accession
        """
        projection_result = ProjectionResults()
        location = _get_variation_location(variation, require_refget=True)

        input_vrs_id: str = variation.id  # type: ignore

        _logger.debug(
            "Attempting projection for %s using %s:%d-%d",
            input_vrs_id,
            genomic_ac,
            location.start,
            location.end,
        )

        # Use cool-seq-tool to get MANE c./p. representations, falling back to
        # the longest compatible remaining transcript when MANE is unavailable
        # or incompatible.
        try:
            result = self._run_async_projection(
                self._resolve_genomic_mane_c_p(
                    genomic_ac,
                    location.start,
                    location.end,
                ),
                timeout_message="Projection failed: coordinate mapping timed out",
                failure_message="Projection failed: error during coordinate mapping",
                log_context=(
                    "cool-seq-tool projection for "
                    f"{genomic_ac}:{location.start}-{location.end}"
                ),
            )
        except ProjectionError as e:
            projection_result.add(
                ProjectionFailure.from_error(source_id=variation.id, error=e)
            )
            return projection_result

        if result is None:
            # No compatible transcript is an expected no-op, not a failure.
            msg = f"Projection skipped for {input_vrs_id}: no compatible transcript found at {genomic_ac}:{location.start}-{location.end}"
            _logger.info(msg)

            projection_result.add(
                ProjectionNotApplicable(
                    source_id=variation.id,
                    reason=msg,
                    destination_molecule_type=None,
                )
            )
            return projection_result

        transcript_projection_result = self._project_genomic_to_transcript(
            input_vrs_id,
            variation,
            result.cdna,
            genomic_ac,
        )
        projection_result.add(transcript_projection_result)
        if isinstance(transcript_projection_result, ProjectedVariation):
            tx_allele = transcript_projection_result.destination_variation
            cdna_start, cdna_end = _cdna_pos_to_transcript_pos(result.cdna)
            protein_projection = self._project_transcript_to_protein(
                tx_allele.id,
                result.cdna,
                result.protein,
                cdna_start,
                cdna_end,
                tx_allele.state,
            )
            if protein_projection:
                projection_result.add(protein_projection)

        _logger.debug(
            "Projection finished for %s transcript_id=%s",
            input_vrs_id,
            transcript_projection_result.destination_variation.id
            if isinstance(transcript_projection_result, ProjectedVariation)
            else None,
        )
        return projection_result

    def _project_transcript_variant(
        self,
        variation: SupportedVrsVariation,
        transcript_ac: str,
    ) -> ProjectionResults:
        """Project a direct transcript variant to its associated protein."""
        projection_result = ProjectionResults()
        location = _get_variation_location(variation)

        input_vrs_id: str = variation.id  # type: ignore
        try:
            result = self._run_async_projection(
                self._resolve_transcript_to_protein_metadata(
                    transcript_ac, location.start, location.end
                ),
                timeout_message="Projection failed: transcript metadata lookup timed out",
                failure_message="Projection failed: error during transcript metadata lookup",
                log_context=(
                    f"Transcript projection metadata lookup for {transcript_ac}:{location.start}-{location.end}"
                ),
            )
        except ProjectionError as e:
            projection_result.add(
                ProjectionFailure.from_error(source_id=variation.id, error=e)
            )
            return projection_result
        try:
            cdna, protein = result  # type: ignore[misc]
        except (TypeError, ValueError):
            projection_result.add(
                ProjectionNotApplicable(
                    variation.id,
                    f"Projection skipped: no CDS/protein metadata for transcript {transcript_ac}",
                    models.MoleculeType.PROTEIN,
                )
            )
            return projection_result
        if cdna is None:
            projection_result.add(
                ProjectionNotApplicable(
                    variation.id,
                    f"Projection skipped: no CDS/protein metadata for transcript {transcript_ac}",
                    models.MoleculeType.PROTEIN,
                )
            )
            return projection_result

        cdna_state = _get_transcript_literal_state(self.dp, variation)
        protein_projection_result = self._project_transcript_to_protein(
            input_vrs_id,
            cdna,
            protein,
            location.start,
            location.end,
            cdna_state,
            missing_protein_message=(
                "Projection skipped: no associated protein accession for transcript "
                f"{transcript_ac}"
            ),
        )
        projection_result.add(protein_projection_result)
        return projection_result

    def project_variations(
        self,
        variation: SupportedVrsVariation,
    ) -> ProjectionResults:
        """Get variations which can be projected from the provided variation

        :param variation: input variant
        :return: result class containing successfully-generated mappings as well as failures
        """
        if not isinstance(variation, models.Allele):
            raise TypeError("Projection is currently supported for alleles only")
        refseq_accession = _get_refseq_accession(self.dp, variation)
        if not refseq_accession:
            msg = f"Projection skipped for {variation.id}: could not resolve RefSeq accession for {variation.location.sequenceReference.refgetAccession}"
            _logger.info(msg)
            return ProjectionResults(failures=[ProjectionFailure(variation.id, msg)])

        molecule_type = get_molecule_type(variation.location.sequenceReference, self.dp)
        match molecule_type:
            case models.MoleculeType.GENOMIC:
                return self._project_genomic_variant(variation, refseq_accession)
            case models.MoleculeType.RNA:
                return self._project_transcript_variant(variation, refseq_accession)
            case _:
                return ProjectionResults(
                    not_applicable=[
                        ProjectionNotApplicable(
                            source_id=variation.id,
                            reason=f"Projection unsupported for molecule type: {molecule_type}",
                            destination_molecule_type=None,
                        )
                    ]
                )
