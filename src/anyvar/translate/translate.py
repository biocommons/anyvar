"""Provide base properties for Translator classes."""

from abc import ABC, abstractmethod
from typing import Optional

from anyvar.utils.types import VrsVariation


class TranslatorSetupException(Exception):
    """Indicates failure to create translator instance (e.g. invalid params provided)"""


class TranslatorConnectionException(Exception):
    """Indicates failure to connect to translator instance (e.g. REST endpoint not
    responding)
    """


class TranslationException(Exception):
    """Indicates failure to translate provided term into known variation structure."""


class _Translator(ABC):
    """Base Translator class."""

    @abstractmethod
    def translate_variation(self, var: str, **kwargs):
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
        :raises TranslationException: if translation is unsuccessful, either because
            the submitted variation is malformed, or because VRS-Python doesn't support
            its translation.
        """
        raise NotImplementedError

    @abstractmethod
    def translate_allele(self, var: str) -> Optional[VrsVariation]:
        """Translate provided variation text into a normalized VRS object.

        :param var: user-provided string describing or referencing a variation.
        :returns: VRS variation object if able to normalize
        :raises TranslatorConnectionException: if translation request returns error
        """
        raise NotImplementedError

    @abstractmethod
    def translate_cnv(self, var: str) -> Optional[VrsVariation]:
        """Translate provided variation text into a normalized VRS object.

        :param var: user-provided string describing or referencing a variation.
        :returns: VRS variation object if able to normalize
        :raises TranslatorConnectionException: if translation request returns error
        """
        raise NotImplementedError

    @abstractmethod
    def translate_vcf_row(self, assembly: str, coords: str) -> Optional[VrsVariation]:
        """Translate VCF-like data to a normalized VRS object.

        :param coords: string formatted a la "<chr>-<pos>-<ref>-<alt>"
        :param assembly: The assembly used in `coords`
        :return: VRS variation (using VRS-Python class) if translation is successful
        """
        raise NotImplementedError

    @abstractmethod
    def get_sequence_id(self, accession_id: str) -> str:
        """Get GA4GH sequence identifier for provided accession ID

        :param accession_id: ID to convert
        :return: equivalent GA4GH sequence ID
        :raise: KeyError if no equivalent ID is available
        """
        raise NotImplementedError
