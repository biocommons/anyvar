import pytest


base_url = "/positions"

tests = {
    "PIgWDzCiuWewlIJiVR": {
        "end": 22,
        "start": 11,
        "type": "Interval"
    },
    "PIrk-ewn-cBR4wt-MB": {
        "end": 22,
        "start": 11,
        "start_offset": 3,
        "type": "Interval"
    },
    "PNQfaXq4COj3XUOt7Q": {
        "inner": {
            "end": 200,
            "start": 110,
            "type": "Interval"
        },
        "outer": {
            "end": 210,
            "start": 100,
            "type": "Interval"
        },
        "type": "NestedInterval"
    },
    "PRpsBqHp0D5fCpxlQX": {
        "end": {
            "end": 210,
            "start": 200,
            "type": "Interval"
        },
        "start": {
            "end": 110,
            "start": 100,
            "type": "Interval"
        },
        "type": "RangedInterval"
    },
    "PI__kfythhz1MMxCAU": {
        "end": None,
        "start": 200,
        "type": "Interval"
    }
}


@pytest.mark.parametrize("id", tests.keys())
def test_00_put(client, id):
    resp = client.put(base_url, json=tests[id])
    assert resp.status_code == 200

    j = resp.json
    assert j["data"]["id"] == id
    

@pytest.mark.parametrize("id", tests.keys())
def test_10_get(client, id):
    resp = client.get(base_url + "/" + id)
    assert resp.status_code == 200

    j = resp.json
    assert j["data"] == tests[id]
    

def test_20_search(client):
    resp = client.get(base_url)
    assert resp.status_code == 200

    j = resp.json
    assert j["data"] == tests
