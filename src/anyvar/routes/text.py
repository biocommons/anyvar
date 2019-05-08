from connexion import NoContent

from ..globals import get_manager


def put(body):
    m = get_manager()
    
    request = body
    defn = request.pop("definition")
    
    t = m.translate_text(defn=defn)
    m.add_text(t)

    result = {
        "messages": [],
        "data": t.as_dict()
    }
    
    return result, 200


def get(id):
    m = get_manager()
    result = {
        "messages": [],
        "data": m.get_text(id).as_dict()
    }
    
    return result, 200
