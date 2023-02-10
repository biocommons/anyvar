import logging

from ..globals import get_dataproxy

_logger = logging.getLogger(__name__)


def get(alias):
    dp = get_dataproxy()
    md = dp.get_metadata(alias)
    return md, 200
