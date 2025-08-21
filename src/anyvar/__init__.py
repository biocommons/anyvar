"""Import basic AnyVar objects."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version(__package__)  # type: ignore (the try/except block handles the case where `__package__` is `None`)
except PackageNotFoundError:  # pragma: no cover
    # package is not installed
    __version__ = "unknown"

from .anyvar import AnyVar  # isort:skip
