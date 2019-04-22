from connexion import NoContent

from .. import __version__

from ..globals import get_vmc_manager

import hgvs
import biocommons.seqrepo



def search():
    vm = get_vmc_manager()

    return {
        "version": __version__,
        "translator": vm.info(),
        }, 200
