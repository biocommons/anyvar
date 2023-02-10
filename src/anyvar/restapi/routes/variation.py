from connexion import NoContent

from ..globals import get_anyvar


def put(body):
    av = get_anyvar()
    translator = av.translator

    request = body

    result = {
        "messages": [],
        "data": None,
    }

    tv = translator.create_text_variation(request["definition"])
    av = translator.create_allele(request["definition"])

    if av["data"]:
        result = av
        result["messages"].append("text variation id:" + tv["id"])
    else:
        result = tv
        result["messages"] += av["messages"]

    return result, 201


def get(id):
    av = get_anyvar()
    try:
        v = av.get_object(id, deref=True)
        return v.as_dict(), 200
    except KeyError:
        return NoContent, 404
