"""Provide tools for and implementations of AnyVar storage backends."""

DEFAULT_STORAGE_URI = "postgresql://postgres@localhost:5432/anyvar"

from .abc import _Storage
