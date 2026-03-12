"""Project variants across the central dogma: genomic (g.) ↔ coding (c.) ↔ protein (p.)

Uses cool-seq-tool to resolve MANE transcripts and map coordinates between
molecule types. Follows the same pattern as liftover.py for storing projected
variants and their mappings.
"""

import asyncio
import logging
import threading

from cool_seq_tool import CoolSeqTool
from cool_seq_tool.schemas import CoordinateType
from ga4gh.core import ga4gh_identify
from ga4gh.vrs import models
from ga4gh.vrs.dataproxy import _DataProxy

from anyvar.core.metadata import VariationMapping, VariationMappingType
from anyvar.core.objects import VrsVariation
from anyvar.storage.base import Storage

_logger = logging.getLogger(__name__)


class ProjectionError(Exception):
    """Indicates a failure during variant projection."""


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
) -> models.Allele | None:
    """Construct a VRS Allele from a RefSeq accession and inter-residue coordinates.

    :param dp: SeqRepo DataProxy instance
    :param refseq_accession: RefSeq accession (e.g. "NM_004333.6")
    :param start: inter-residue start position
    :param end: inter-residue end position
    :return: VRS Allele with computed GA4GH ID, or None if construction fails
    """
    refget_accession = _get_refget_accession(dp, refseq_accession)
    if not refget_accession:
        _logger.warning("Could not resolve refget accession for %s", refseq_accession)
        return None

    # Fetch the reference sequence at the projected position
    try:
        ref_sequence = dp.get_sequence(
            f"ga4gh:{refget_accession}", start=start, end=end
        )
    except Exception:
        _logger.exception(
            "Failed to fetch sequence for %s:%d-%d", refseq_accession, start, end
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
    ga4gh_identify(location, in_place="always")

    allele = models.Allele(
        type="Allele",
        location=location,
        state=models.LiteralSequenceExpression(
            type="LiteralSequenceExpression",
            sequence=models.sequenceString(ref_sequence),
        ),
    )
    ga4gh_identify(allele, in_place="always")
    return allele


def _store_projected_variant(
    storage: Storage,
    source_id: str,
    projected_variant: models.Allele,
    mapping_type: VariationMappingType,
) -> None:
    """Store a projected variant and create bidirectional mappings.

    :param storage: Storage instance
    :param source_id: VRS ID of the source variant
    :param projected_variant: the projected VRS Allele
    :param mapping_type: type of mapping (TRANSCRIBE_TO or TRANSLATE_TO)
    """
    projected_id: str = projected_variant.id  # type: ignore
    storage.add_objects([projected_variant])
    storage.add_mapping(
        VariationMapping(
            source_id=source_id,
            dest_id=projected_id,
            mapping_type=mapping_type,
        )
    )
    storage.add_mapping(
        VariationMapping(
            source_id=projected_id,
            dest_id=source_id,
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

        # Get the RefSeq genomic accession (NC_xxx)
        alt_ac = _get_refseq_accession(self.dp, refget_accession)
        if not alt_ac or not alt_ac.startswith("NC_"):
            _logger.debug("Skipping projection: %s is not a genomic accession", alt_ac)
            return None  # silently skip non-genomic variants

        input_vrs_id: str = variation.id  # type: ignore

        # Use cool-seq-tool to get MANE c. and p. representations
        try:
            future = asyncio.run_coroutine_threadsafe(
                self.cst.mane_transcript.grch38_to_mane_c_p(
                    alt_ac=alt_ac,
                    start_pos=start,
                    end_pos=end,
                    coordinate_type=CoordinateType.INTER_RESIDUE,
                ),
                self._loop,
            )
            result = future.result(timeout=30)
        except Exception:
            _logger.exception(
                "cool-seq-tool projection failed for %s:%d-%d", alt_ac, start, end
            )
            return ["Projection failed: error during coordinate mapping"]

        if result is None:
            _logger.debug("No MANE transcript found for %s:%d-%d", alt_ac, start, end)
            return None  # no MANE data — not an error

        messages: list[str] = []

        # Build and store coding (c.) variant
        cdna = result.cdna
        if cdna.refseq:
            cdna_allele = _build_allele(self.dp, cdna.refseq, cdna.pos[0], cdna.pos[1])
            if cdna_allele:
                _store_projected_variant(
                    storage,
                    input_vrs_id,
                    cdna_allele,
                    VariationMappingType.TRANSCRIBE_TO,
                )

                # Build and store protein (p.) variant from c. variant
                protein = result.protein
                if protein and protein.refseq:
                    protein_allele = _build_allele(
                        self.dp, protein.refseq, protein.pos[0], protein.pos[1]
                    )
                    if protein_allele:
                        cdna_id: str = cdna_allele.id  # type: ignore
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
                    _logger.debug("No protein representation returned for %s", alt_ac)
            else:
                messages.append(f"Could not build coding variant for {cdna.refseq}")
        else:
            _logger.debug(
                "No RefSeq cDNA accession in projection result for %s", alt_ac
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
        except Exception:
            _logger.exception("Unexpected error during projection of %s", variation.id)
            return ["Projection failed: unexpected error"]
