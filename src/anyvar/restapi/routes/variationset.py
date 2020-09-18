import ga4gh.vr

from ..globals import get_anyvar


def put(body):
    request = body
    defn = request.pop("definition")

    av = get_anyvar()

    messages = []

    if "members" in defn:
        return {"messages": ["unsupported"]}, 400

    if "member_ids" in defn:
        vs = ga4gh.vr.models.VariationSet(member_ids=defn["member_ids"])
        vs.id = ga4gh.vr.computed_id(vs)
        m.storage.variationsets[vs.id] = vs
    
    result = {
        "messages": messages,
        "data": vs.as_dict(),
    }
    
    return result, 200


def get(id):
    av = get_anyvar()
    return m.storage.variationsets[id].as_dict(), 200

