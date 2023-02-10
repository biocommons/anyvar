from ..globals import get_anyvar


def get(vartype):
    av = get_anyvar()
    if vartype == "substitution":
        out = av.object_store.substitution_count()
    elif vartype == "deletion":
        out = av.object_store.deletion_count()
    elif vartype == "insertion":
        out = av.object_store.insertion_count()
    elif vartype == "all":
        out = len(av.object_store)
    return out, 200
