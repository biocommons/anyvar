"""Import basic AnyVar objects."""

import logging

import pkg_resources

_logger = logging.getLogger(__name__)

__all__ = ["AnyVar"]


try:
    __version__ = pkg_resources.get_distribution(__name__).version
    _logger.info("Package %s, version = %s", __name__, __version__)
except pkg_resources.DistributionNotFound:
    __version__ = "unknown"
finally:
    del pkg_resources


from .anyvar import AnyVar  # isort:skip
