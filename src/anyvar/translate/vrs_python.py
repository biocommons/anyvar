"""Normalize incoming variation descriptions with the VRS-Python library."""
from typing import Optional
from os import environ

from ga4gh.vrs.extras.translator import Translator
from ga4gh.vrs.dataproxy import _SeqRepoDataProxyBase, SeqRepoDataProxy
from biocommons.seqrepo import SeqRepo

from . import TranslatorConnectionException, _Translator
from anyvar.utils.types import VrsPythonVariation

SEQREPO_ROOT_DIR = environ.get("SEQREPO_ROOT_DIR", "/usr/local/share/seqrepo/latest")


class VrsPythonTranslator(_Translator):
    """Translator layer using VRS-Python Translator class."""

    def __init__(self, seqrepo_proxy: Optional[_SeqRepoDataProxyBase] = None) -> None:
        """Initialize VRS-Python translator.

        :param seqrepo_proxy: existing SR proxy instance if available. If not given,
            try to construct a data proxy using local data at the file address
            defined under the environment variable ``SEQREPO_ROOT_DIR``, or
            ``/usr/local/share/seqrepo/latest`` by default.
        """
        if not seqrepo_proxy:
            seqrepo_proxy = SeqRepoDataProxy(SeqRepo(SEQREPO_ROOT_DIR))
        self.tlr = Translator(
            data_proxy=seqrepo_proxy
        )

    def translate(self, var: str) -> Optional[VrsPythonVariation]:
        """Translate provided variation text into a normalized VRS object.

        :param var: user-provided string describing or referencing a variation.
        :returns: VRS variation object if able to normalize
        :raises TranslatorConnectionException: if translation request returns error
        """
        return self.tlr.translate_from(var)

    def translate_vcf_row(self, coords: str) -> Optional[VrsPythonVariation]:
        """Translate VCF-like data to a normalized VRS object.

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
        result = self.tlr.data_proxy.translate_sequence_identifier(
            accession_id, "ga4gh"
        )
        return result[0]
