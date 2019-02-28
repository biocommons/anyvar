from connexion import NoContent

from . import __version__

from .globals import get_translator

import hgvs
import biocommons.seqrepo



def search():
    translator = get_translator()

    return {
        "version": __version__,
        "translator": translator.info(),
        }, 200
