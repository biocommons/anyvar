"""Provide base properties for Translator classes."""
from abc import ABC, abstractmethod
from typing import Dict


class TranslatorSetupException(Exception):
    """Indicates failure to create translator instance (e.g. invalid params provided)"""


class TranslatorConnectionException(Exception):
    """Indicates failure to connect to translator instance (e.g. REST endpoing not
    responding)
    """


class TranslationException(Exception):
    """Indicates failure to translate provided term into known variation structure."""


class _Translator(ABC):

    @abstractmethod
    def translate(self, var: str, **kwargs: Dict):
        raise NotImplementedError
