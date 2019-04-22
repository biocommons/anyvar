from ..globals import get_vmc_manager

import vmc


def put(body):
    request = body
    defn = request.pop("definition")

    vm = get_vmc_manager()

    messages = []

    if "members" in defn:
        return {"messages": ["unsupported"]}, 400

    if "member_ids" in defn:
        vs = vmc.models.VariationSet(member_ids=defn["member_ids"])
        vs.id = vmc.computed_id(vs)
        vm.storage[vs.id] = vs
    
    result = {
        "messages": messages,
        "data": vs.as_dict(),
    }
    
    return result, 200


def get(id):
    vm = get_vmc_manager()
    return vm.storage[id].as_dict(), 200

