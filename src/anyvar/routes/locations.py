from connexion import NoContent

from ..globals import get_vmc_manager


def get(id):
    # if id not in (sr instance)
    #     return NoContent, 404

    vm = get_vmc_manager()

    if id not in vm.storage:
        return NoContent, 404

    return vm.storage[id].as_dict(), 200


def search(body):
    vm = get_vmc_manager()
    return [vm.storage[id] for id in vm.storage.keys() if id.startswith("VMC:GL")], 404
