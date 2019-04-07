from connexion import NoContent

from ..globals import get_bm, get_translator


def put(body):
    translator = get_translator()
    bm = get_bm()

    request = body

    result = {
        "messages": [],
        "data": None,
    }

    tv = translator.create_text_variation(request["definition"])
    av = translator.create_allele(request["definition"])

    if av["data"]:
        result = av
        result["messages"].append("text variation id:" + tv["id"])
    else:
        result = tv
        result["messages"] += av["messages"]

    return result, 201


def get(id):
    bm = get_bm()

    # as hgvs too?
    if id not in bm.alleles:
        return NoContent, 404

    return bm.alleles[id].as_dict(), 200
