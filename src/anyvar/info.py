from connexion import NoContent

from . import __version__
from .globals import translator

import hgvs
import biocommons.seqrepo
from vmc.extra.seqrepo import _get_seqrepo

sr = _get_seqrepo()


def search():
    return {
        "version": __version__,
        "translator": translator.info(),
        }, 200
