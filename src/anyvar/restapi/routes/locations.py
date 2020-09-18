from connexion import NoContent

from ..globals import get_manager


def get(id):
    m = get_manager()

    if id not in m.storage.locations:
        return NoContent, 404

    return m.storage.locations[id].as_dict(), 200


def search(body):
    m = get_manager()
    return [m.storage.locations[id] for id in vm.storage.locations], 200
