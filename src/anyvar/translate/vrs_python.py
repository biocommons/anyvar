"""Normalize incoming variation descriptions with the VRS-Python library."""

from os import environ

from ga4gh.vrs import models
from ga4gh.vrs.dataproxy import _DataProxy, create_dataproxy
from ga4gh.vrs.extras.translator import AlleleTranslator, CnvTranslator

from anyvar.translate.translate import TranslationError
from anyvar.utils.types import SupportedVariationType, VrsVariation

from . import _Translator


class VrsPythonTranslator(_Translator):
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
        self.allele_tlr = AlleleTranslator(data_proxy=seqrepo_proxy)
        self.cnv_tlr = CnvTranslator(data_proxy=seqrepo_proxy)

    def translate_variation(
        self, var: str, **kwargs
    ) -> models.Allele | models.CopyNumberCount | models.CopyNumberChange | None:
        """Translate provided variation text into a VRS Variation object.

        :param var: user-provided string describing or referencing a variation.
        :param input_type: The type of variation for `var`.
        :kwargs:
            input_type (SupportedVariationType): The type of variation for `var`.
                If not provided, will first try to translate to allele and then
                copy number
            copies (int) - The number of copies for VRS Copy Number Count
            copy_change (models.CopyChange) - The EFO code for VRS COpy Number Change
        :returns: VRS variation object if able to translate
        :raises TranslationError: if translation is unsuccessful, either because
            the submitted variation is malformed, or because VRS-Python doesn't support
            its translation.
        """
        variation = None
        input_type = kwargs.get("input_type")
        if input_type == SupportedVariationType.ALLELE:
            variation = self.translate_allele(var)
        elif input_type in {
            SupportedVariationType.COPY_NUMBER_CHANGE,
            SupportedVariationType.COPY_NUMBER_COUNT,
        }:
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

    def translate_allele(self, var: str) -> models.Allele | None:
        """Translate provided variation text into a VRS Allele object.

        :param var: user-provided string describing or referencing a variation.
        :returns: VRS variation object if able to translate
        :raises TranslationError: if translation is unsuccessful, either because
            the submitted variation is malformed, or because VRS-Python doesn't support
            its translation.
        """
        try:
            return self.allele_tlr.translate_from(var, fmt=None)
        except ValueError as e:
            msg = f"{var} isn't supported by the VRS-Python AlleleTranslator."
            raise TranslationError(msg) from e

    def translate_cnv(
        self, var: str, **kwargs
    ) -> models.CopyNumberCount | models.CopyNumberChange | None:
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
            return self.cnv_tlr.translate_from(var, fmt=None, **kwargs)
        except ValueError as e:
            msg = f"{var} isn't supported by the VRS-Python CnvTranslator."
            raise TranslationError(msg) from e

    def translate_vcf_row(self, assembly: str, coords: str) -> VrsVariation | None:
        """Translate VCF-like data to a VRS object.

        :param coords: string formatted a la "<chr>-<pos>-<ref>-<alt>"
        :param assembly: The assembly used in `coords`
        :return: VRS variation (using VRS-Python class) if translation is successful
        """
        return self.allele_tlr.translate_from(coords, "gnomad", assembly_name=assembly)

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
