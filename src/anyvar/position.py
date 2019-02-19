from connexion import NoContent

from ._backend import bm


store = {}


def get(id):
    if id not in store:
        return NoContent, 404
    return store[id], 200


def post(body):
    request = body
    result = {
        "messages": [],
        "data": request,
    }

    return result, 201



def search(body):
    return NoContent, 404
