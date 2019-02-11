import base64
import hashlib
import json


positions = {}

PREFIXES = {
    "Interval": "PI",
    "RangedInterval": "PR",
    "NestedInterval": "PN"
    }


def _generate_id(d):
    s = json.dumps(d, sort_keys=True)
    digest = hashlib.sha512(s.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest[:12]).decode("ascii")

def _make_response(data, messages):
    return {"data": data, "messages": messages}


def get(id):
    return _make_response(data=positions[id], messages=[]), 200

def put(body):
    messages = []
    pfx = PREFIXES[body["type"]]
    id = pfx + _generate_id(body)
    positions[id] = body
    resp = _make_response(messages=messages, data={"id": id})
    return resp, 200

def search():
    return _make_response(data=positions, messages=[]), 200

