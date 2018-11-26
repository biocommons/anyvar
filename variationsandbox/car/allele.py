from connexion import NoContent

from vmc.extra.alleleregistry import AlleleRegistryClient


arc = AlleleRegistryClient(
    base_url="http://reg.test.genome.network",
    login="testuser",
    password="testuser"
    )


def get(id):
    d = arc.get_allele_by_id(id=id)
    return d, 200

# hgvs = "NC_000010.11:g.87894077C>T"
def search(hgvs):
    d = arc.get_allele_by_hgvs(hgvs=hgvs)
    return d, 200
