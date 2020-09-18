from connexion import NoContent

from ..globals import get_anyvar


def get(id):
    av = get_anyvar()

    if id not in av.storage.locations:
        return NoContent, 404

    return m.storage.locations[id].as_dict(), 200


def search(body):
    av = get_anyvar()
    return [av.storage.locations[id] for id in av.storage.locations], 200
