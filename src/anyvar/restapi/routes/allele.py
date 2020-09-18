from connexion import NoContent

from ..globals import get_anyvar


def put(body):
    request = body
    defn = request.pop("definition")
    fmt = request.pop("format")

    messages = []

    av = get_anyvar()
    v = av.put_allele(defn=defn, fmt=fmt)

    result = {
        "messages": messages,
        "data": v.as_dict(),
    }

    return result, 200


def get(id):
    av = get_anyvar()

    try:
        v = av.get_object(id, deref=True)
    except KeyError:
        return None, 404

    result = {
        "messages": [],
        "data": v.as_dict()
    }

    return result, 200
