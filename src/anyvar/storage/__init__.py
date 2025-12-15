"""Provide tools for and implementations of AnyVar storage backends."""

from .base_storage import Storage

DEFAULT_STORAGE_URI = "postgresql://postgres@localhost:5432/anyvar"

__all__ = ["DEFAULT_STORAGE_URI", "Storage"]
