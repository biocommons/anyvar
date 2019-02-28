from connexion import NoContent

from .globals import bm, translator


def put(body):
    request = body

    defn = request.pop("definition")
    fmt = request.pop("accept_formats")
    norm = request.pop("normalize")
    val = request.pop("validate")

    result = {
        "messages": [],
        "data": None,
    }
    
    if fmt == "hgvs_allele":
        a = bm.add_hgvs_allele(defn)
        result["messages"].append("Allele normalized; shifted 7 residues")
        result["id"] = a.id
        result["data"] = a.as_dict()
    else:
        return "unsupported format ({})".format(fmt), 400

    return result, 201


def get(id):
    # as hgvs too?
    if id not in bm.alleles:
        return NoContent, 404

    return bm.alleles[id].as_dict(), 200
