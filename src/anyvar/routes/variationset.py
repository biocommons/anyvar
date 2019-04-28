import vmc

from ..globals import get_manager


def put(body):
    request = body
    defn = request.pop("definition")

    m = get_manager()

    messages = []

    if "members" in defn:
        return {"messages": ["unsupported"]}, 400

    if "member_ids" in defn:
        vs = vmc.models.VariationSet(member_ids=defn["member_ids"])
        vs.id = vmc.computed_id(vs)
        m.storage.variationsets[vs.id] = vs
    
    result = {
        "messages": messages,
        "data": vs.as_dict(),
    }
    
    return result, 200


def get(id):
    m = get_manager()
    return m.storage.variationsets[id].as_dict(), 200

