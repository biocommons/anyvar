"""Normalize incoming variation descriptions with the VRS-Python library."""

from os import environ

from ga4gh.vrs import models
from ga4gh.vrs.dataproxy import _DataProxy, create_dataproxy
from ga4gh.vrs.extras.translator import AlleleTranslator, CnvTranslator

from anyvar.translate.translate import TranslationError, Translator
from anyvar.utils import types


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
            self.dp = create_dataproxy(seqrepo_uri)
        self.allele_tlr = AlleleTranslator(data_proxy=self.dp)
        self.cnv_tlr = CnvTranslator(data_proxy=self.dp)

    def translate_variation(self, var: str, **kwargs) -> types.VrsVariation:
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
        if input_type == types.SupportedVariationType.ALLELE:
            variation = self.translate_allele(var, **kwargs)
        elif input_type in (
            types.SupportedVariationType.COPY_NUMBER_CHANGE,
            types.SupportedVariationType.COPY_NUMBER_COUNT,
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
