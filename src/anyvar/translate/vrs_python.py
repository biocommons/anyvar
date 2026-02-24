"""Normalize incoming variation descriptions with the VRS-Python library."""

import logging
from os import environ
from warnings import warn

from biocommons.seqrepo import SeqRepo
from bioutils.accessions import coerce_namespace
from ga4gh.vrs import models
from ga4gh.vrs.dataproxy import SeqRepoDataProxy, _DataProxy, create_dataproxy
from ga4gh.vrs.extras.translator import AlleleTranslator, CnvTranslator

from anyvar.core.objects import VrsVariation
from anyvar.restapi.schema import SupportedVariationType
from anyvar.translate.base import TranslationError, Translator

_logger = logging.getLogger(__name__)


class WindowedSeqRepoDataProxy(SeqRepoDataProxy):
    """SeqRepo proxy with fixed-size window caching.

    Optimizes repeated small range queries by caching a single fixed-size sequence
    window and serving subsequent sub-range requests from memory when possible.

    .. warning::

       This API is still experimental, and is subject to change.

    If a request falls outside the cached window or exceeds the configured chunk size,
    it is delegated directly to SeqRepo.
    """

    def __init__(self, sr: SeqRepo) -> None:
        """Initialize DataProxy instance.

        :param sr: SeqRepo instance
        """
        warn(
            "WindowedSeqRepoDataProxy is experimental, and its module path and API may change in future releases",
            category=FutureWarning,
            stacklevel=2,
        )
        super().__init__(sr)
        self._chunk_size = 100000
        self._cached_ids = set()
        # initialize window start/end with illegal values so that first request is always a miss
        self._seq_start, self._seq_end = -1, -1
        self._seq = ""
        _logger.info("Initialized windowed-caching seqrepo dataproxy")

    def _get_sequence(
        self, identifier: str, start: int | None = None, end: int | None = None
    ) -> str:
        """Return a sequence slice, using a fixed-size window cache when possible.

        For small range queries (< self._chunk_size), this method fetches and caches
        a contiguous window of sequence starting at ``start``. Subsequent requests
        that fall within the cached window are served directly from memory.

        The cache stores:
          - a single sequence window
          - its genomic start/end bounds
          - identifiers known to resolve to the same underlying sequence

        This optimization improves performance for workloads exhibiting
        spatial locality (many nearby small slice requests).
        """
        namespaced_id = coerce_namespace(identifier)

        # Delegate large or unbounded requests directly to SeqRepo
        if (start is None or end is None) or (end - start >= self._chunk_size):
            return self.sr.fetch_uri(namespaced_id, start, end)

        # cache hit
        if (
            namespaced_id in self._cached_ids
            and start >= self._seq_start
            and end <= self._seq_end
        ):
            return self._seq[start - self._seq_start : end - self._seq_start]

        sequence = self.sr.fetch_uri(namespaced_id, start, start + self._chunk_size)
        if self._seq == "" or self._seq != sequence:
            self._cached_ids = {namespaced_id}
            self._seq_start = start
            self._seq_end = start + self._chunk_size
            self._seq = sequence
        elif sequence == self._seq:
            # update the known aliases for this sequence and try again
            self._cached_ids.add(namespaced_id)
        return self._get_sequence(namespaced_id, start, end)


class VrsPythonTranslator(Translator):
    """Translator layer using VRS-Python Translator class."""

    def __init__(
        self, seqrepo_proxy: _DataProxy | None = None, disable_healthcheck: bool = False
    ) -> None:
        """Initialize VRS-Python translator.

        If an existing SeqRepo data proxy is not provided, use the VRS-Python
        ``create_dataproxy`` function to construct one. The following URI patterns
        can be used to specify a local file instance or an address to REST service:

        * seqrepo+file:///path/to/seqrepo/root
        * seqrepo+:../relative/path/to/seqrepo/root
        * seqrepo+http://localhost:5000/seqrepo
        * seqrepo+https://somewhere:5000/seqrepo

        We'll pass the value defined under the environment variable
        ``SEQREPO_DATAPROXY_URI``, and default to local service
        (``"seqrepo+http://localhost:5000/seqrepo"``) if it's undefined.

        :param seqrepo_proxy: existing SR proxy instance if available.
        :param disable_healthcheck: Whether or not to disable the health check for REST
            dataproxy
        """
        if not seqrepo_proxy:
            seqrepo_uri = environ.get(
                "SEQREPO_DATAPROXY_URI", "seqrepo+http://localhost:5000/seqrepo"
            )
            self.dp = create_dataproxy(
                seqrepo_uri, disable_healthcheck=disable_healthcheck
            )
        else:
            self.dp = seqrepo_proxy
        self.allele_tlr = AlleleTranslator(data_proxy=self.dp)
        self.cnv_tlr = CnvTranslator(data_proxy=self.dp)

    def translate_variation(self, var: str, **kwargs) -> VrsVariation:
        """Translate provided variation text into a VRS Variation object.

        :param var: user-provided string describing or referencing a variation.
        :param input_type: The type of variation for `var`.
        :keyword types.VrsVariation input_type: The type of variation for `var`. If
            not provided, will first try to translate to allele and then copy number
        :keyword int copies: The number of copies for VRS Copy Number Count
        :keyword models.CopyChange copy_change: The EFO code for VRS COpy Number Change
        :keyword ReferenceAssembly assembly_name: Assembly name for ``var``.
            Only used when ``var`` uses gnomad format.
        :returns: VRS variation object
        :raises TranslationError: if translation is unsuccessful, either because
            the submitted variation is malformed, or because VRS-Python doesn't support
            its translation.
        """
        input_type = kwargs.get("input_type")
        if input_type == SupportedVariationType.ALLELE:
            variation = self.translate_allele(var, **kwargs)
        elif input_type in (
            SupportedVariationType.COPY_NUMBER_CHANGE,
            SupportedVariationType.COPY_NUMBER_COUNT,
        ):
            variation = self.translate_cnv(var, **kwargs)
        else:
            # Try allele then copy number
            try:
                variation = self.translate_allele(var)
            except TranslationError:
                try:
                    variation = self.translate_cnv(var, **kwargs)
                except TranslationError as e:
                    msg = f"{var} isn't supported by the VRS-Python AlleleTranslator or CnvTranslator."
                    raise TranslationError(msg) from e

        return variation

    def translate_allele(self, var: str, **kwargs) -> models.Allele:
        """Translate provided variation text into a VRS Allele object.

        :param var: user-provided string describing or referencing a variation.
        :kwargs:
            assembly_name(str) -> Assembly name for ``var``.
            Only used when ``var`` uses gnomad format.
            Defaults to "GRCh38". Must be "GRCh38" or "GRCh7"
            VRS-Python sets a default, but we should set a default just in case
            VRS-Python ever changes the default.
        :returns: VRS variation object if able to translate
        :raises TranslationError: if translation is unsuccessful, either because
            the submitted variation is malformed, or because VRS-Python doesn't support
            its translation.
        """
        try:
            return self.allele_tlr.translate_from(var, fmt=None, **kwargs)  # type: ignore (this will always return a models.Allele instance, or raise a ValueError)
        except ValueError as e:
            msg = f"{var} isn't supported by the VRS-Python AlleleTranslator."
            raise TranslationError(msg) from e

    def translate_cnv(
        self, var: str, **kwargs
    ) -> models.CopyNumberCount | models.CopyNumberChange:
        """Translate provided variation text into a VRS object.

        :param var: user-provided string describing or referencing a variation.
        :kwargs:
            copies(int) - The number of copies for VRS Copy Number Count
            copy_change (models.CopyChange) - The EFO code for VRS COpy Number Change
        :returns: VRS variation object if able to translate
        :raises TranslationError: if translation is unsuccessful, either because
            the submitted variation is malformed, or because VRS-Python doesn't support
            its translation.
        """
        try:
            return self.cnv_tlr.translate_from(var, fmt=None, **kwargs)  # type: ignore (this will always return a models.CopyNumberCount | models.CopyNumberChange instance, or raise a ValueError)
        except ValueError as e:
            msg = f"{var} isn't supported by the VRS-Python CnvTranslator."
            raise TranslationError(msg) from e

    def get_sequence_id(self, accession_id: str) -> str:
        """Get GA4GH sequence identifier for provided accession ID

        :param accession_id: ID to convert
        :return: equivalent GA4GH sequence ID
        :raise: KeyError if no equivalent ID is available
        """
        result = self.allele_tlr.data_proxy.translate_sequence_identifier(
            accession_id, "ga4gh"
        )
        return result[0]
