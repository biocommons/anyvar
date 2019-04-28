from connexion import NoContent

import anyvar
import vmc



def search():
    rv = {
        "version": anyvar.__version__,
        "vmc-python": {
            "version": vmc.__version__
        },
    }

    return rv, 200
