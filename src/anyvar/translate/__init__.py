"""Provide proxy classes and other tools for translation middleware."""

from .base import (
    TranslationError,
    Translator,
    TranslatorConnectionError,
    TranslatorSetupError,
)

__all__ = [
    "TranslationError",
    "Translator",
    "TranslatorConnectionError",
    "TranslatorSetupError",
]
