"""Normalize incoming variation descriptions with the VRS-Python library."""

import logging
from os import environ

from bioutils.accessions import coerce_namespace
from ga4gh.vrs import models
from ga4gh.vrs.dataproxy import SeqRepoDataProxy, _DataProxy, create_dataproxy
from ga4gh.vrs.extras.translator import AlleleTranslator, CnvTranslator

from anyvar.core.objects import VrsVariation
from anyvar.restapi.schema import SupportedVariationType
from anyvar.translate.base import TranslationError, Translator

_logger = logging.getLogger(__name__)


class SequentialSeqRepoDataProxy(SeqRepoDataProxy):  # noqa: D101
    def __init__(self, sr) -> None:  # noqa: ANN001
        """Initialize DataProxy instance.

        :param sr: SeqRepo instance
        """
        super().__init__(sr)
        self._chunk_size = 10000
        self._seq_id, self._seq_start, self._seq_end, self._seq = set(), -1, -1, ""

    def _get_sequence(
        self, identifier: str, start: int | None = None, end: int | None = None
    ) -> str:
        namespaced_id = coerce_namespace(identifier)
        if (start is None or end is None) or (end - start >= self._chunk_size):
            return self.sr.fetch_uri(namespaced_id, start, end)
        if (
            namespaced_id in self._seq_id
            and start >= self._seq_start
            and end <= self._seq_end
        ):
            return self._seq[start - self._seq_start : end - self._seq_start]
        sequence = self.sr.fetch_uri(namespaced_id, start, start + self._chunk_size)
        if self._seq == "" or self._seq != sequence:
            self._seq_id = {namespaced_id}
            self._seq_start = start
            self._seq_end = start + self._chunk_size
            self._seq = sequence
        elif sequence == self._seq:
            self._seq_id.add(namespaced_id)
        return self._get_sequence(namespaced_id, start, end)


class VrsPythonTranslator(Translator):
    """Translator layer using VRS-Python Translator class."""

    def __init__(self, seqrepo_proxy: _DataProxy | None = None) -> None:
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
        """
        if not seqrepo_proxy:
            seqrepo_uri = environ.get(
                "SEQREPO_DATAPROXY_URI", "seqrepo+http://localhost:5000/seqrepo"
            )
            seqrepo_proxy = create_dataproxy(seqrepo_uri)
            _logger.info("Creating sequential dataproxy")
        self.dp = seqrepo_proxy
        self.allele_tlr = AlleleTranslator(data_proxy=seqrepo_proxy)
        self.cnv_tlr = CnvTranslator(data_proxy=seqrepo_proxy)

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
