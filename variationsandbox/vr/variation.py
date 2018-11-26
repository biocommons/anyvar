from connexion import NoContent

from vmc.extra.bundlemanager import BundleManager

bm = BundleManager()

def post(body):
    defn = body.pop("definition")
    fmt = body.pop("format")
    if fmt == "hgvs_allele":
        a = bm.add_hgvs_allele(defn)
        return a.as_dict(), 201
    return "unsupported format ({})".format(fmt), 400

def get(id):
    if id not in bm.alleles:
        return NoContent, 404

    return bm.alleles[id].as_dict(), 200
