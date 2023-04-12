"""Provide base properties for Translator classes."""
from abc import ABC, abstractmethod
from typing import Optional

from anyvar.utils.types import VrsPythonVariation

DEFAULT_TRANSLATE_URI = "http://localhost:8000/variation/"


class TranslatorSetupException(Exception):
    """Indicates failure to create translator instance (e.g. invalid params provided)"""


class TranslatorConnectionException(Exception):
    """Indicates failure to connect to translator instance (e.g. REST endpoing not
    responding)
    """


class TranslationException(Exception):
    """Indicates failure to translate provided term into known variation structure."""


class _Translator(ABC):
    """Base Translator class."""

    @abstractmethod
    def translate(self, var: str) -> Optional[VrsPythonVariation]:
        """Translate provided variation text into a normalized VRS object.

        :param var: user-provided string describing or referencing a variation.
        :returns: VRS variation object if able to normalize
        :raises TranslatorConnectionException: if translation request returns error
        """
        raise NotImplementedError

    @abstractmethod
    def translate_vcf_row(self, coords: str) -> Optional[VrsPythonVariation]:
        """Translate VCF-like data to a normalized VRS object.

        :param coords: string formatted a la "<chr>-<pos>-<ref>-<alt>"
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
