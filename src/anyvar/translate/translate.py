"""Provide base properties for Translator classes."""
from abc import ABC, abstractmethod
from typing import Dict


class Translator(ABC):

    @abstractmethod
    def translate_from(self, var: str, **kwargs: Dict):
        raise NotImplementedError


class TranslatorConnectionException(Exception):
    """Indicates failure to connect to translator instance (e.g. REST endpoing not responding)"""


class TranslationException(Exception):
    """Indicates failure to translate provided term into known variation structure."""
