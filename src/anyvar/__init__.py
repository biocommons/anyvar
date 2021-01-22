# -*- coding: utf-8 -*-

import logging

import pkg_resources

_logger = logging.getLogger(__name__)

__all__ = "AnyVar".split()


try:
    __version__ = pkg_resources.get_distribution(__name__).version
    _logger.info(f"Package {__name__} version = {__version__}")
except pkg_resources.DistributionNotFound:
    __version__ = "unknown"
finally:
    del pkg_resources


from .anyvar import AnyVar
from .restapi.webapp import run