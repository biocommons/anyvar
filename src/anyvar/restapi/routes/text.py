from connexion import NoContent

from ..globals import get_anyvar


def put(body):
    av = get_anyvar()
    request = body
    defn = request.pop("definition")
    v = av.create_text(defn)
    id = av.put_object(v)
    result = {
        "object": v.as_dict(),
        "messages": [],
    }
    return result, 200


def get(id):
    av = get_anyvar()
    result = {
        "messages": [],
        "data": av.get_object(id).as_dict()
    }
    return result, 200
