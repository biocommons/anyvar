from connexion import NoContent

def post(body):
    v = {"blah": 1}
    return v, 201

def get(id):
    v = {"id": id}
    return v
