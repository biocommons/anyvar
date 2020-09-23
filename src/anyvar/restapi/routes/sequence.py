import logging
import re

from connexion import NoContent, request

from ..globals import get_seqrepo
from .utils import get_sequence_ids, problem

_logger = logging.getLogger(__name__)


def get(alias, start=None, end=None):
    if start is not None and end is not None:
        if start > end:
            return problem(422, "Invalid coordinates: start > end")
    sr = get_seqrepo()
    seq_ids = get_sequence_ids(sr, alias)
    if not seq_ids:
        return NoContent, 404
    if len(seq_ids) > 1:
        return problem(422, f"Multiple sequences exist for alias '{alias}'")
    seq_id = seq_ids[0]
    return sr.sequences.fetch(seq_id, start, end), 200
