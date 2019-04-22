from connexion import NoContent

from ..globals import get_vmc_manager

import vmc


def put(body):
    request = body
    defn = request.pop("definition")
    fmt = request.pop("format")
    norm = False
    use_canonical_sequence = False

    messages = []

    vm = get_vmc_manager()

    if fmt == "ga4gh":
        a = vm.add_ga4gh_allele(defn)
    elif fmt == "hgvs":
        a = vm.add_hgvs_allele(defn)
    elif fmt == "beacon":
        pass
    elif fmt == "gnomad":
        pass
    elif fmt == "spdi":
        pass
    else:
        return "unsupported format ({})".format(fmt), 400
    
    if norm:
        n = normalize(a)
        if n != a:
            messages += ["Variation was normalized"]
            vm.storage[n.id] = n

    if use_canonical_sequence:
        a_cs = replace_reference(a)
        a_cs.id = vmc.computed_id(a_cs)
        if a_cs != a:
            messages += ["Reference sequence was canonicalized"]
            vm.storage[a_cs.id] = a_cs

    a.location = vm.storage[a.location_id]

    result = {
        "messages": messages,
        "data": a.as_dict(),
    }
    
    return result, 200


def get(id):
    vm = get_vmc_manager()
    result = {
        "messages": [],
        "data": vm.storage[id].as_dict()
    }
    
    return result, 200
