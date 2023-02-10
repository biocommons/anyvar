"""Get or retrieve allele object in storage."""
from anyvar.translate.translate import TranslationException

from ..globals import get_anyvar


def put(body):
    request = body
    defn = request.pop("definition")

    av = get_anyvar()
    result = {"object": None, "messages": []}
    try:
        v = av.translator.translate(var=defn)
    except TranslationException:
        result["messages"].append(f"Unable to translate {defn}")
    except NotImplementedError:
        result["messages"].append(
            f"Variation class for {defn} is currently unsupported."
        )
    else:
        v_id = av.put_object(v)
        result["object"] = v.as_dict()
        result["object_id"] = v_id
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
