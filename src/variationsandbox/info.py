from connexion import NoContent

from . import __version__
import hgvs
import biocommons.seqrepo
from vmc.extra.seqrepo import _get_seqrepo

sr = _get_seqrepo()


def search():
    return {
        "version": __version__,
        "dependencies": {
            "hgvs": {
                "version": hgvs.__version__,
                },
            "biocommons.seqrepo": {
                "version": biocommons.seqrepo.__version__,
                "instance_directory": sr._root_dir,
                },
            },
        }, 200
