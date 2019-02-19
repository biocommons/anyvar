import pytest


base_url = "/variation"

tests = {
    "PIgWDzCiuWewlIJiVR": {
        "data": 

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
