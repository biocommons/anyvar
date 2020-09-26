from connexion import NoContent

from ..globals import get_anyvar


def put(body):
    request = body
    defn = request.pop("definition")
    fmt = request.pop("format")

    messages = []

    av = get_anyvar()
    v = av.translator.translate_from(var=defn, fmt=fmt)
    id = av.put_object(v)

    result = {
        "object": v.as_dict(),
        "messages": messages,
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
