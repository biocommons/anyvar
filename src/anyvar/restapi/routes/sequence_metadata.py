import logging

from connexion import NoContent

from ..globals import get_dataproxy
from .utils import get_sequence_ids, problem


_logger = logging.getLogger(__name__)


def get(alias):
    dp = get_dataproxy()
    md = dp.get_metadata(alias)
    return md, 200
