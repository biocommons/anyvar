from connexion import NoContent

from ..globals import get_anyvar


def get(id):
    av = get_anyvar()
    try:
        return av.get_object(id).as_dict(), 200
    except KeyError:
        return NoContent, 404


#def search(body):
#    av = get_anyvar()
#   return [av.storage.locations[id] for id in av.storage.locations], 200
