from connexion import NoContent

from ._backend import bm


def get(id):
    # if id not in (sr instance)
    #     return NoContent, 404

    if id not in bm.locations:
        return NoContent, 404

    return bm.locations[id].as_dict(), 200



def search(body):
    return NoContent, 404
