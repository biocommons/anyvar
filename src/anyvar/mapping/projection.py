"""Project variants across the central dogma: genomic (g.) ↔ coding (c.) ↔ protein (p.)

Uses cool-seq-tool to resolve MANE transcripts and map coordinates between
molecule types. Follows the same pattern as liftover.py for storing projected
variants and their mappings.
"""

import asyncio
import concurrent.futures
import logging
import threading
from typing import Protocol

from bioutils import sequences as bioutils_sequences
from bioutils.sequences import TranslationTable
from cool_seq_tool import CoolSeqTool
from cool_seq_tool.mappers.mane_transcript import CdnaRepresentation
from cool_seq_tool.schemas import CoordinateType
from ga4gh.core import ga4gh_identify
from ga4gh.vrs import models, normalize
from ga4gh.vrs.dataproxy import _DataProxy
from ga4gh.vrs.normalize import denormalize_reference_length_expression

from anyvar.core.metadata import VariationMapping, VariationMappingType
from anyvar.core.objects import VrsVariation
from anyvar.storage.base import Storage

_logger = logging.getLogger(__name__)

_CODON_LENGTH = 3


class ProjectionError(Exception):
    """Indicates a failure during variant projection."""


class _ProteinRepresentation(Protocol):
    """Protein projection result shape used by projection helpers."""

    refseq: str | None
    pos: tuple[int, int]


def _get_refseq_accession(dp: _DataProxy, refget_accession: str) -> str | None:
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
    # Prefer NC_ (genomic) accessions, then NM_, then any
    for prefix in ("refseq:NC_", "refseq:NM_", "refseq:NP_"):
        for alias in aliases:
            if alias.startswith(prefix):
                return alias.removeprefix("refseq:")
    # Fall back to first alias
    return aliases[0].removeprefix("refseq:")


def _get_refget_accession(dp: _DataProxy, refseq_accession: str) -> str | None:
    """Convert a RefSeq accession (NC_/NM_/NP_) to a refget accession (SQ.xxx).

    :param dp: SeqRepo DataProxy instance
    :param refseq_accession: RefSeq accession (e.g. "NM_004333.6")
    :return: refget accession (without ga4gh: prefix) or None
    """
    try:
        aliases = dp.translate_sequence_identifier(refseq_accession, "ga4gh")
    except KeyError:
        _logger.debug("No refget accession found for %s", refseq_accession)
        return None
    if not aliases:
        return None
    # aliases are like "ga4gh:SQ.xxx" — strip the prefix
    return aliases[0].removeprefix("ga4gh:")


def _build_allele(
    dp: _DataProxy,
    refseq_accession: str,
    start: int,
    end: int,
    state: models.LiteralSequenceExpression,
) -> models.Allele | None:
    """Construct and normalize a VRS Allele.

    :param dp: SeqRepo DataProxy instance
    :param refseq_accession: RefSeq accession (e.g. "NM_004333.6")
    :param start: inter-residue start position
    :param end: inter-residue end position
    :param state: literal projected replacement state
    :return: normalized VRS Allele with computed GA4GH ID, or None if construction fails
    """
    refget_accession = _get_refget_accession(dp, refseq_accession)
    if not refget_accession:
        _logger.warning("Could not resolve refget accession for %s", refseq_accession)
        return None

    if start < 0 or end < 0:
        _logger.warning(
            "Skipping allele construction for %s:%d-%d",
            refseq_accession,
            start,
            end,
        )
        return None

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


def _project_cdna_literal_state(
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


def _protein_projection_error(protein: _ProteinRepresentation) -> ProjectionError:
    """Build a consistent expected-failure error for protein projection."""
    return ProjectionError(
        "Projection skipped: could not derive alternate protein state for "
        f"{protein.refseq}"
    )


def _is_single_residue(amino_acid: object) -> bool:
    """Return whether a translated amino acid is specific enough to project."""
    # "X" represents an unknown/ambiguous amino acid
    return isinstance(amino_acid, str) and len(amino_acid) == 1 and amino_acid != "X"


def _select_translation_table_for_codon(
    dp: _DataProxy,
    protein: _ProteinRepresentation,
    ref_codon: str,
) -> TranslationTable:
    """Select a translation table only when the reference codon is validated."""
    if not isinstance(ref_codon, str) or len(ref_codon) != _CODON_LENGTH:
        raise _protein_projection_error(protein)
    if not protein.refseq:
        raise _protein_projection_error(protein)

    refget_accession = _get_refget_accession(dp, protein.refseq)
    if not refget_accession:
        raise _protein_projection_error(protein)

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

    if not _is_single_residue(reference_residue):
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

    if not _is_single_residue(ref_amino_acid):
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
    cdna: CdnaRepresentation,
    protein: _ProteinRepresentation,
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

    refget_accession = _get_refget_accession(dp, cdna.refseq)
    if not refget_accession:
        raise _protein_projection_error(protein)
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
    if not _is_single_residue(alt_amino_acid):
        raise _protein_projection_error(protein)

    try:
        return models.LiteralSequenceExpression(
            type="LiteralSequenceExpression",
            sequence=models.sequenceString(alt_amino_acid),
        )
    except Exception as exc:
        raise _protein_projection_error(protein) from exc


def _is_utr_variant(cdna: CdnaRepresentation) -> str | None:
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
    """Projects variants across the central dogma using MANE transcript selection.

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

    def _project_genomic_variant(
        self,
        variation: VrsVariation,
        storage: Storage,
    ) -> list[str] | None:
        """Project a genomic variant to coding and protein representations.

        :param variation: genomic VRS variation
        :param storage: Storage instance
        :return: list of warning messages, or None on success
        """
        try:
            refget_accession = variation.location.sequenceReference.refgetAccession
            start = variation.location.start
            end = variation.location.end
        except AttributeError:
            return ["Projection unsupported: variant lacks sequence location details"]

        # Only handle int positions (not Range)
        if not isinstance(start, int) or not isinstance(end, int):
            return ["Projection unsupported for variants with Range positions"]

        input_vrs_id: str = variation.id  # type: ignore

        # Get the RefSeq genomic accession (NC_xxx)
        alt_ac = _get_refseq_accession(self.dp, refget_accession)
        if not alt_ac or not alt_ac.startswith("NC_"):
            _logger.debug("Skipping projection: %s is not a genomic accession", alt_ac)
            return None  # silently skip non-genomic variants

        _logger.debug(
            "Attempting projection for %s using %s:%d-%d",
            input_vrs_id,
            alt_ac,
            start,
            end,
        )

        # Use cool-seq-tool to get MANE c. and p. representations
        future: concurrent.futures.Future | None = None
        try:
            future = asyncio.run_coroutine_threadsafe(
                self.cst.mane_transcript.grch38_to_mane_c_p(
                    alt_ac=alt_ac,
                    start_pos=start,
                    end_pos=end,
                    coordinate_type=CoordinateType.INTER_RESIDUE,
                    # TODO set try_longest_compatible to True
                ),
                self._loop,
            )
            result = future.result(timeout=30)
        except concurrent.futures.TimeoutError:
            if future is not None:
                future.cancel()
            _logger.warning(
                "cool-seq-tool projection timed out for %s:%d-%d",
                alt_ac,
                start,
                end,
            )
            return ["Projection failed: coordinate mapping timed out"]
        except Exception:
            _logger.exception(
                "cool-seq-tool projection failed for %s:%d-%d", alt_ac, start, end
            )
            return ["Projection failed: error during coordinate mapping"]

        if result is None:
            # No compatible MANE transcript is an expected no-op, not a failure.
            _logger.info(
                "Projection skipped for %s: no MANE transcript found at %s:%d-%d",
                input_vrs_id,
                alt_ac,
                start,
                end,
            )
            return None  # no MANE data — not an error

        messages: list[str] = []
        cdna_id: str | None = None
        protein_id: str | None = None

        # Build and store coding (c.) variant
        cdna = result.cdna
        if cdna.refseq:
            # cdna.pos is CDS-relative; add coding_start_site for transcript coords.
            cdna_start = cdna.pos[0] + cdna.coding_start_site
            cdna_end = cdna.pos[1] + cdna.coding_start_site
            cdna_state = _project_cdna_literal_state(self.dp, variation, cdna)
            cdna_allele = _build_allele(
                self.dp,
                cdna.refseq,
                cdna_start,
                cdna_end,
                cdna_state,
            )
            if cdna_allele:
                cdna_id = cdna_allele.id  # type: ignore[assignment]
                _store_projected_variant(
                    storage,
                    input_vrs_id,
                    cdna_allele,
                    VariationMappingType.TRANSCRIBE_TO,
                )

                # Skip protein mapping for UTR variants
                utr_region = _is_utr_variant(cdna)
                if utr_region:
                    _logger.info(
                        "Skipping protein projection for %s: variant in %s UTR",
                        cdna.refseq,
                        utr_region.replace("_", "' "),
                    )
                else:
                    # Build and store protein (p.) variant from c. variant
                    protein = result.protein
                    if protein and protein.refseq:
                        try:
                            protein_state = _derive_protein_substitution_state(
                                self.dp,
                                cdna,
                                protein,
                                cdna_start,
                                cdna_end,
                                cdna_state,
                            )
                        except ProjectionError as exc:
                            # Keep the stored transcript mapping; only protein is skipped.
                            _logger.info("%s", exc)
                            messages.append(str(exc))
                            return messages
                        protein_allele = _build_allele(
                            self.dp,
                            protein.refseq,
                            protein.pos[0],
                            protein.pos[1],
                            protein_state,
                        )
                        if protein_allele:
                            protein_id = protein_allele.id  # type: ignore[assignment]
                            # Protein mappings start from the projected transcript allele.
                            _store_projected_variant(
                                storage,
                                cdna_id,
                                protein_allele,
                                VariationMappingType.TRANSLATE_TO,
                            )
                        else:
                            messages.append(
                                f"Could not build protein variant for {protein.refseq}"
                            )
                    else:
                        _logger.debug(
                            "No protein representation returned for %s", alt_ac
                        )
            else:
                messages.append(f"Could not build coding variant for {cdna.refseq}")
        else:
            _logger.debug(
                "No RefSeq cDNA accession in projection result for %s", alt_ac
            )

        _logger.debug(
            "Projection finished for %s transcript_id=%s protein_id=%s message_count=%d",
            input_vrs_id,
            cdna_id,
            protein_id,
            len(messages),
        )
        return messages if messages else None

    def add_mappings(
        self,
        variation: VrsVariation,
        storage: Storage,
    ) -> list[str] | None:
        """Project a variant to other molecule types and store mappings.

        For genomic variants, projects to coding (TRANSCRIBE_TO) and protein
        (TRANSLATE_TO) representations using MANE transcript selection.

        This method catches and suppresses major error cases and communicates
        results as warning messages.

        :param variation: variation to project
        :param storage: Storage instance
        :return: list of warning messages, or None if completely successful
        """
        # Currently only genomic→coding→protein projection is supported
        # Future: add coding→genomic and coding→protein paths
        try:
            return self._project_genomic_variant(variation, storage)
        except ProjectionError as exc:
            _logger.info("Projection failed for %s: %s", variation.id, exc)
            return [str(exc)]
        except Exception:
            _logger.exception("Unexpected error during projection of %s", variation.id)
            return ["Projection failed: unexpected error"]
