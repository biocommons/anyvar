from connexion import NoContent

from .globals import get_bm


def get(id):
    # if id not in (sr instance)
    #     return NoContent, 404

    bm = get_bm()

    if id not in bm.locations:
        return NoContent, 404

    return bm.locations[id].as_dict(), 200



def search(body):
    return NoContent, 404
