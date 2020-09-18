from connexion import NoContent

from ..globals import get_manager


def put(body):
    request = body
    defn = request.pop("definition")
    fmt = request.pop("format")

    messages = []

    m = get_manager()
    a = m.translate_allele(defn=defn, fmt=fmt)
    m.add_allele(a)
    
    result = {
        "messages": messages,
        "data": a.as_dict(),
    }
    
    return result, 200


def get(id):
    m = get_manager()

    try:
        a = m.get_allele(id)
    except KeyError as e:
        return None, 404
        
    result = {
        "messages": [],
        "data": a.as_dict()
    }
    
    return result, 200
