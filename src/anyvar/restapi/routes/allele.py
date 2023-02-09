"""Get or retrieve allele object in storage."""
from anyvar.translate.translate import TranslationException

from ..globals import get_anyvar


def put(body):
    request = body
    defn = request.pop("definition")

    messages = []

    av = get_anyvar()
    try:
        v = av.translator.translate(var=defn)
    except TranslationException:
        result = {
            "object": None,
            "messages": [f"Unable to translate {defn}"]
        }
        return result, 200

    id = av.put_object(v)

    result = {
        "object": v.as_dict(),
        "object_id": id,
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
