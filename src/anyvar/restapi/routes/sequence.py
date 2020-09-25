import logging

from ..globals import get_dataproxy
from .utils import get_sequence_ids, problem

_logger = logging.getLogger(__name__)


def get(alias, start=None, end=None):
    if start is not None and end is not None:
        if start > end:
            return problem(422, "Invalid coordinates: start > end")
    dp = get_dataproxy()
    return dp.get_sequence(alias, start, end), 200

