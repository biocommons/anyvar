from anyvar.storage.postgres import PostgresObjectStore

from ..globals import get_anyvar


def get_ga4gh_alias(seqrepo_data_proxy, accession):
    md = seqrepo_data_proxy.get_metadata(accession)
    aliases = md.get("aliases")
    ga4gh_id = None
    if aliases:
        ga4gh_id = ([a for a in aliases if a.startswith("ga4gh")] or [None])[0]
    return ga4gh_id

def search(accession, start, stop):
    av = get_anyvar()
    try:
        ga4gh_id = get_ga4gh_alias(av.data_proxy, accession)
    except KeyError:
        return [], 404

    alleles = []
    if ga4gh_id:
        if isinstance(av.object_store, (PostgresObjectStore)):
            alleles = av.object_store.find_alleles(ga4gh_id, start, stop)
        else:
            raise NotImplementedError()

    inline_alleles = list()
    for allele in alleles:
        inline_alleles.append(av.get_object(allele["_id"], deref=True).as_dict())
    return inline_alleles, 200
