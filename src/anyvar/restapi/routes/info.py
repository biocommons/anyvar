from connexion import NoContent

import anyvar
import ga4gh.vrs



def search():
    rv = {
        "anyvar": {
            "version": anyvar.__version__,
            },
        "ga4gh.vrs": {
            "version": ga4gh.vrs.__version__
        },
    }

    return rv, 200
