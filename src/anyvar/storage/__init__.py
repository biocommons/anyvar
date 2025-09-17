"""Provide tools for and implementations of AnyVar storage backends."""

from .abc import _Storage

DEFAULT_STORAGE_URI = "postgresql://postgres@localhost:5432/anyvar"
