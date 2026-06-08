"""Provide base properties for Translator classes."""

from abc import ABC, abstractmethod

from ga4gh.vrs.dataproxy import _DataProxy
from ga4gh.vrs.models import Allele

from anyvar.core.objects import SupportedVrsVariation


class TranslatorSetupError(Exception):
    """Indicates failure to create translator instance (e.g. invalid params provided)"""


class TranslatorConnectionError(Exception):
    """Indicates failure to connect to translator instance (e.g. REST endpoint not
    responding)
    """


class TranslationError(Exception):
    """Indicates failure to translate provided term into known variation structure."""


class Translator(ABC):
    """Base Translator class.

    Use for
    * Translating incoming variant expressions to VRS
    * Acquiring reference accessions for incoming sequence descriptions/references

    """

    dp: _DataProxy

    @abstractmethod
    def translate_variation(self, var: str, **kwargs) -> SupportedVrsVariation:
        """Translate provided variation text into a VRS Variation object.

        At the moment, only VRS Alleles are supported.

        :param var: user-provided string describing or referencing a variation.
        :param kwargs: Additional translation options.
        :returns: VRS variation object
        :raises TranslationError: if translation is unsuccessful, either because
            the submitted variation is malformed, uses an unsupported identifier format,
            fails validation checks, or is not supported by VRS-Python.
        """
        raise NotImplementedError

    @abstractmethod
    def translate_allele(self, var: str, **kwargs) -> Allele:
        """Translate provided variation text into a normalized VRS Allele object.

        :param var: user-provided string describing or referencing a variation.
        :param kwargs: Additional translation options.
        :returns: VRS Allele object
        :raises TranslationError: if translation is unsuccessful, either because
            the submitted variation is malformed, uses an unsupported identifier format,
            fails validation checks, or is not supported by VRS-Python.
        """
        raise NotImplementedError

    @abstractmethod
    def translate_allele_to_format(
        self, allele: Allele, fmt: str, **kwargs
    ) -> list[str]:
        """Translate a VRS Allele to one or more identifiers in the requested format.

        :param allele: VRS Allele to translate.
        :param fmt: Target identifier format (e.g. hgvs, spdi)
        :param kwargs: Additional translation options.
        :return: List of translated identifiers in the requested format.
        :raises TranslationError: If translation is unsuccessful because required
            reference sequence information cannot be resolved, the allele is invalid,
            or the requested format is unsupported by VRS-Python.
        """

    @abstractmethod
    def get_sequence_id(self, accession_id: str) -> str:
        """Get GA4GH sequence identifier for provided accession ID

        :param accession_id: ID to convert
        :return: equivalent GA4GH sequence ID
        :raise: KeyError if no equivalent ID is available
        """
        raise NotImplementedError
