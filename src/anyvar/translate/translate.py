"""Provide base properties for Translator classes."""

from abc import ABC, abstractmethod

from ga4gh.vrs.dataproxy import _DataProxy

from anyvar.utils.types import VrsVariation


class TranslatorSetupError(Exception):
    """Indicates failure to create translator instance (e.g. invalid params provided)"""


class TranslatorConnectionError(Exception):
    """Indicates failure to connect to translator instance (e.g. REST endpoint not
    responding)
    """


class TranslationError(Exception):
    """Indicates failure to translate provided term into known variation structure."""


class Translator(ABC):
    """Base Translator class."""

    dp: _DataProxy

    @abstractmethod
    def translate_variation(self, var: str, **kwargs) -> VrsVariation:
        """Translate provided variation text into a VRS Variation object.

        :param var: user-provided string describing or referencing a variation.
        :param input_type: The type of variation for `var`.
        :kwargs:
            input_type (types.VrsVariation): The type of variation for `var`.
                If not provided, will first try to translate to allele and then
                copy number
            copies (int) - The number of copies for VRS Copy Number Count
            copy_change (models.CopyChange) - The EFO code for VRS COpy Number Change
            assembly_name(str) -> Assembly name for ``var``.
                Only used when ``var`` uses gnomad format.
                Defaults to "GRCh38". Must be "GRCh38" or "GRCh7"
                VRS-Python sets a default, but we should set a default just in case
                VRS-Python ever changes the default.
        :returns: VRS variation object
        :raises TranslationError: if translation is unsuccessful, either because
            the submitted variation is malformed, or because VRS-Python doesn't support
            its translation.
        """
        raise NotImplementedError

    @abstractmethod
    def translate_allele(self, var: str) -> VrsVariation | None:
        """Translate provided variation text into a normalized VRS object.

        :param var: user-provided string describing or referencing a variation.
        :returns: VRS variation object if able to normalize
        :raises TranslatorConnectionError: if translation request returns error
        """
        raise NotImplementedError

    @abstractmethod
    def translate_cnv(self, var: str) -> VrsVariation | None:
        """Translate provided variation text into a normalized VRS object.

        :param var: user-provided string describing or referencing a variation.
        :returns: VRS variation object if able to normalize
        :raises TranslatorConnectionError: if translation request returns error
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
