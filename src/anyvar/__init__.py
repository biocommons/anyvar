"""Import basic AnyVar objects."""

import logging
from importlib.metadata import PackageNotFoundError, version

_logger = logging.getLogger(__name__)

__all__ = ["AnyVar"]


try:
    __version__ = version(__name__)
    _logger.info("Package %s, version = %s", __name__, __version__)
except PackageNotFoundError:
    __version__ = "unknown"


from .anyvar import AnyVar  # isort:skip
