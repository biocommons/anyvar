from connexion import NoContent

from ..globals import get_anyvar
from anyvar.storage.postgres import PostgresObjectStore

def search(accession, start, stop):
    av = get_anyvar()
    try:
        md = av.data_proxy.get_metadata(accession)
    except KeyError:
        return [], 404

    alleles = []
    aliases = md.get("aliases")
    if aliases:
        ga4gh_id = ([a for a in aliases if a.startswith("ga4gh")] or [None])[0]
        if ga4gh_id:
            if isinstance(av.object_store, (PostgresObjectStore)):
                alleles = av.object_store.find_alleles(ga4gh_id, start, stop)
            else:
                raise NotImplementedError()

    inline_alleles = list()
    for allele in alleles:
        inline_alleles.append(av.get_object(allele["_id"], deref=True).as_dict())
    return inline_alleles, 200
