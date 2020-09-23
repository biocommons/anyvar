import logging

from connexion import NoContent

from ..globals import get_seqrepo
from .utils import get_sequence_ids, problem


_logger = logging.getLogger(__name__)


def get(alias):
    sr = get_seqrepo()

    seq_ids = get_sequence_ids(sr, alias)
    if not seq_ids:
        return NoContent, 404
    if len(seq_ids) > 1:
        return problem(422, f"Multiple sequences exist for alias '{alias}'")
    seq_id = seq_ids[0]

    seqinfo = sr.sequences.fetch_seqinfo(seq_id=seq_id)
    aliases = sr.aliases.find_aliases(seq_id=seq_id)

    md = {
        "added": seqinfo["added"],
        "aliases": [f"{a['namespace']}:{a['alias']}" for a in aliases],
        "alphabet": seqinfo["alpha"],
        "length": seqinfo["len"],
        }

    return md, 200
