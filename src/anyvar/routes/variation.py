from connexion import NoContent

from ..globals import get_vmc_manager


def put(body):
    translator = get_translator()
    vm = get_vmc_manager()

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
    vm = get_vmc_manager()

    # as hgvs too?
    if id not in vm.alleles:
        return NoContent, 404

    return vm.storage[id].as_dict(), 200
