from connexion import NoContent

import vmc

from ..globals import get_vmc_manager


def put(body):
    vm = get_vmc_manager()
    
    request = body
    defn = request.pop("definition")
    
    v = vmc.models.Text(definition=defn)
    v.id = vmc.computed_id(v)
    vm.storage[v.id] = v
    
    result = {
        "messages": [],
        "data": v.as_dict()
    }
    
    return result, 200


def get(id):
    vm = get_vmc_manager()
    result = {
        "messages": [],
        "data": vm.storage[id].as_dict()
    }
    
    return result, 200
