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
from collections.abc import Awaitable
from dataclasses import dataclass
from typing import Protocol

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

from anyvar.core.metadata import VariationMapping, VariationMappingType
from anyvar.core.objects import VrsVariation
from anyvar.storage.base import Storage

_logger = logging.getLogger(__name__)

_CODON_LENGTH = 3
_ASYNC_TIMEOUT = 30
_REFSEQ_TRANSCRIPT_PREFIXES = ("NM_", "NR_", "XM_", "XR_")


class ProjectionError(Exception):
    """Indicates a failure during variant projection."""


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


@dataclass(frozen=True)
class _ProjectedTranscriptAllele:
    """Projected transcript allele metadata needed for protein projection."""

    vrs_id: str
    start: int
    end: int
    state: models.LiteralSequenceExpression


def _get_variation_location(
    variation: VrsVariation,
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


def _refget_to_refseq_accession(dp: _DataProxy, refget_accession: str) -> str | None:
    """Convert a refget accession (SQ.xxx) to a RefSeq accession (NC_/NM_/NP_).

    :param dp: SeqRepo DataProxy instance
    :param refget_accession: refget accession (e.g. "SQ.xxx")
    :return: RefSeq accession or None if not found
    """
    ga4gh_id = f"ga4gh:{refget_accession}"
    try:
        aliases = dp.translate_sequence_identifier(ga4gh_id, "refseq")
    except KeyError:
        _logger.debug("No RefSeq alias found for %s", refget_accession)
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
    variation: VrsVariation,
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
    variation: VrsVariation,
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
    variation: VrsVariation,
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


def _is_refseq_transcript_accession(accession: str) -> bool:
    """Return whether an accession names a RefSeq transcript sequence."""
    return accession.startswith(_REFSEQ_TRANSCRIPT_PREFIXES)


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


def _store_projected_variant(
    storage: Storage,
    source_id: str,
    projected_variant: models.Allele,
    mapping_type: VariationMappingType,
) -> None:
    """Store a projected variant and create a forward mapping.

    :param storage: Storage instance
    :param source_id: VRS ID of the source variant
    :param projected_variant: the projected VRS Allele
    :param mapping_type: type of mapping (TRANSCRIBE_TO or TRANSLATE_TO)
    """
    projected_id: str = projected_variant.id  # type: ignore
    _logger.debug(
        "Persisting projected variant mapping_type=%s source_id=%s dest_id=%s",
        mapping_type.value,
        source_id,
        projected_id,
    )
    storage.add_objects([projected_variant])
    storage.add_mapping(
        VariationMapping(
            source_id=source_id,
            dest_id=projected_id,
            mapping_type=mapping_type,
        )
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

    def close(self, timeout: float = 5.0) -> None:
        """Stop the projector event loop thread."""
        if self._loop.is_closed():
            return

        if self._thread.is_alive():
            self._loop.call_soon_threadsafe(self._loop.stop)
            self._thread.join(timeout=timeout)

            if self._thread.is_alive():
                _logger.warning("Projector event loop thread did not stop cleanly")
                return

        self._loop.close()

    def _run_async_projection(
        self,
        awaitable: Awaitable[object],
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
        transcripts = await self.cst.mane_transcript.uta_db.get_transcripts(
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
        cds_start_end = await self.cst.mane_transcript.uta_db.get_cds_start_end(
            transcript_ac
        )
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

        genomic_tx_data = await self.cst.mane_transcript.uta_db.get_genomic_tx_data(
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
        storage: Storage,
        source_id: str,
        cdna: _CdnaPositionLike,
        protein: _RefSeqPositionLike | None,
        cdna_start: int,
        cdna_end: int,
        cdna_state: models.LiteralSequenceExpression,
        *,
        missing_protein_message: str | None = None,
    ) -> None:
        """Project a transcript allele to protein and store the mapping."""
        utr_region = _is_utr_variant(cdna)
        if utr_region:
            _logger.info(
                "Skipping protein projection for %s: variant in %s UTR",
                cdna.refseq,
                utr_region.replace("_", "' "),
            )
            return

        if not protein or not protein.refseq:
            _logger.debug("No protein representation returned for %s", cdna.refseq)
            if missing_protein_message:
                raise ProjectionError(missing_protein_message)
            return

        protein_state = _derive_protein_substitution_state(
            self.dp,
            cdna,
            protein,
            cdna_start,
            cdna_end,
            cdna_state,
        )

        protein_allele = _build_allele(
            self.dp,
            protein.refseq,
            protein.pos[0],
            protein.pos[1],
            protein_state,
        )
        _store_projected_variant(
            storage,
            source_id,
            protein_allele,
            VariationMappingType.TRANSLATE_TO,
        )

    def _project_genomic_to_transcript(
        self,
        storage: Storage,
        source_id: str,
        variation: VrsVariation,
        cdna: CdnaRepresentation,
        genomic_ac: str,
    ) -> _ProjectedTranscriptAllele | None:
        """Build and store the transcript allele projected from a genomic variant."""
        if not cdna.refseq:
            _logger.debug(
                "No RefSeq cDNA accession in projection result for %s", genomic_ac
            )
            return None

        cdna_start, cdna_end = _cdna_pos_to_transcript_pos(cdna)
        cdna_state = _project_genomic_state_to_cdna_literal(self.dp, variation, cdna)
        cdna_allele = _build_allele(
            self.dp,
            cdna.refseq,
            cdna_start,
            cdna_end,
            cdna_state,
        )

        cdna_id: str = cdna_allele.id  # type: ignore[assignment]
        _store_projected_variant(
            storage,
            source_id,
            cdna_allele,
            VariationMappingType.TRANSCRIBE_TO,
        )
        return _ProjectedTranscriptAllele(
            vrs_id=cdna_id,
            start=cdna_start,
            end=cdna_end,
            state=cdna_state,
        )

    def _project_genomic_variant(
        self,
        variation: VrsVariation,
        storage: Storage,
        genomic_ac: str,
    ) -> None:
        """Project a genomic variant to coding and protein representations.

        :param variation: genomic VRS variation
        :param storage: Storage instance
        :param genomic_ac: pre-resolved genomic RefSeq accession
        """
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
        result = self._run_async_projection(
            self.cst.mane_transcript.grch38_to_mane_c_p(
                alt_ac=genomic_ac,
                start_pos=location.start,
                end_pos=location.end,
                coordinate_type=CoordinateType.INTER_RESIDUE,
                try_longest_compatible=True,
            ),
            timeout_message="Projection failed: coordinate mapping timed out",
            failure_message="Projection failed: error during coordinate mapping",
            log_context=(
                "cool-seq-tool projection for "
                f"{genomic_ac}:{location.start}-{location.end}"
            ),
        )

        if result is None:
            # No compatible transcript is an expected no-op, not a failure.
            _logger.info(
                "Projection skipped for %s: no compatible transcript found at %s:%d-%d",
                input_vrs_id,
                genomic_ac,
                location.start,
                location.end,
            )
            return  # no compatible transcript data -- not an error

        transcript_projection = self._project_genomic_to_transcript(
            storage,
            input_vrs_id,
            variation,
            result.cdna,
            genomic_ac,
        )
        if transcript_projection:
            self._project_transcript_to_protein(
                storage,
                transcript_projection.vrs_id,
                result.cdna,
                result.protein,
                transcript_projection.start,
                transcript_projection.end,
                transcript_projection.state,
            )

        _logger.debug(
            "Projection finished for %s transcript_id=%s",
            input_vrs_id,
            transcript_projection.vrs_id if transcript_projection else None,
        )

    def _project_transcript_variant(
        self,
        variation: VrsVariation,
        storage: Storage,
        transcript_ac: str,
    ) -> None:
        """Project a direct transcript variant to its associated protein."""
        location = _get_variation_location(variation)

        input_vrs_id: str = variation.id  # type: ignore
        result = self._run_async_projection(
            self._resolve_transcript_to_protein_metadata(
                transcript_ac, location.start, location.end
            ),
            timeout_message="Projection failed: transcript metadata lookup timed out",
            failure_message="Projection failed: error during transcript metadata lookup",
            log_context=(
                "Transcript projection metadata lookup for "
                f"{transcript_ac}:{location.start}-{location.end}"
            ),
        )
        try:
            cdna, protein = result  # type: ignore[misc]
        except (TypeError, ValueError):
            msg = (
                "Projection skipped: no CDS/protein metadata for transcript "
                f"{transcript_ac}"
            )
            raise ProjectionError(msg) from None
        if cdna is None:
            msg = (
                "Projection skipped: no CDS/protein metadata for transcript "
                f"{transcript_ac}"
            )
            raise ProjectionError(msg)
        cdna_state = _get_transcript_literal_state(self.dp, variation)

        self._project_transcript_to_protein(
            storage,
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

    def _add_projections_for_refseq_accession(
        self,
        variation: VrsVariation,
        storage: Storage,
        refseq_accession: str,
    ) -> None:
        """Dispatch projection for an already-resolved RefSeq accession."""
        if refseq_accession.startswith("NC_"):
            self._project_genomic_variant(variation, storage, refseq_accession)
            return
        if _is_refseq_transcript_accession(refseq_accession):
            # TODO: consider optionally registering an additional mapping from
            # the user-provided transcript to the corresponding MANE transcript.
            self._project_transcript_variant(variation, storage, refseq_accession)
            return
        _logger.debug(
            "Skipping projection: %s is not a genomic or transcript accession",
            refseq_accession,
        )

    def add_projections(
        self,
        variation: VrsVariation,
        storage: Storage,
    ) -> None:
        """Project a variant to other molecule types and store mappings.

        For genomic variants, projects to coding (TRANSCRIBE_TO) and protein
        (TRANSLATE_TO) representations using cool-seq-tool transcript selection
        with longest-compatible fallback. For transcript variants, projects
        directly to the associated protein.

        This method raises projection errors for warning cases that callers may
        catch and communicate to users.

        TODO: This only supports refseq accessions. Consider another approach.

        :param variation: variation to project
        :param storage: Storage instance
        :raises ProjectionError: if projection is unsupported or fails
        """
        if not isinstance(variation, models.Allele):
            raise ProjectionError(
                "Projection unsupported: only Allele variations are supported"
            )

        location = _get_variation_location(variation, require_refget=True)

        try:
            refseq_accession = _refget_to_refseq_accession(
                self.dp, location.refget_accession
            )
            if not refseq_accession:
                _logger.info(
                    "Projection skipped for %s: could not resolve RefSeq accession "
                    "for %s",
                    variation.id,
                    location.refget_accession,
                )
                return
            self._add_projections_for_refseq_accession(
                variation, storage, refseq_accession
            )
        except ProjectionError as exc:
            _logger.info("Projection failed for %s: %s", variation.id, exc)
            raise
        except Exception:
            _logger.exception("Unexpected error during projection of %s", variation.id)
            raise ProjectionError("Projection failed: unexpected error") from None
