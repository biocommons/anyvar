"""Normalize incoming variation descriptions with the VRS-Python library."""
from os import environ
from typing import Optional

from ga4gh.vrs.dataproxy import _DataProxy, create_dataproxy
from ga4gh.vrs.extras.translator import Translator

from anyvar.translate.translate import TranslationException
from anyvar.utils.types import VrsPythonVariation

from . import _Translator


class VrsPythonTranslator(_Translator):
    """Translator layer using VRS-Python Translator class."""

    def __init__(self, seqrepo_proxy: Optional[_DataProxy] = None) -> None:
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
        self.tlr = Translator(data_proxy=seqrepo_proxy)

    def translate(self, var: str) -> Optional[VrsPythonVariation]:
        """Translate provided variation text into a VRS object.

        :param var: user-provided string describing or referencing a variation.
        :returns: VRS variation object if able to translate
        :raises TranslationException: if translation is unsuccessful, either because
            the submitted variation is malformed, or because VRS-Python doesn't support
            its translation.
        """
        try:
            return self.tlr.translate_from(var)
        except ValueError:
            raise TranslationException(f"{var} isn't supported by the VRS-Python translator.")

    def translate_vcf_row(self, coords: str) -> Optional[VrsPythonVariation]:
        """Translate VCF-like data to a VRS object.

        :param coords: string formatted a la "<chr>-<pos>-<ref>-<alt>"
        :return: VRS variation (using VRS-Python class) if translation is successful
        """
        return self.tlr.translate_from(coords, "gnomad")

    def get_sequence_id(self, accession_id: str) -> str:
        """Get GA4GH sequence identifier for provided accession ID

        :param accession_id: ID to convert
        :return: equivalent GA4GH sequence ID
        :raise: KeyError if no equivalent ID is available
        """
        result = self.tlr.data_proxy.translate_sequence_identifier(accession_id, "ga4gh")
        return result[0]
