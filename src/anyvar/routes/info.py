from connexion import NoContent

import anyvar
import ga4gh.vr



def search():
    rv = {
        "anyvar": {
            "version": anyvar.__version__,
            },
        "ga4gh.vr": {
            "version": ga4gh.vr.__version__
        },
    }

    return rv, 200
