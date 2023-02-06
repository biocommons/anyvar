"""Get or retrieve allele object in storage."""
from anyvar.translate.translate import TranslationException

from ..globals import get_anyvar


def put(body):
    request = body
    defn = request.pop("definition")
    fmt = request.pop("format")

    messages = []

    av = get_anyvar()
    try:
        v = av.translator.translate_from(var=defn, fmt=fmt)
    except TranslationException:
        result = {
            "object": None,
            "messages": [f"Unable to translate {defn}"]
        }
        return result, 200

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
