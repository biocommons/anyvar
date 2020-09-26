"""full-service interface to converting, validating, and registering
biological sequence variation

"""

import collections.abc
import logging

from ga4gh.core import ga4gh_identify
from ga4gh.vrs import models, vr_deref, vr_enref
from ga4gh.vrs.extras.translator import Translator


_logger = logging.getLogger(__name__)


class AnyVar:
    def __init__(self, /, data_proxy, object_store):
        if not isinstance(object_store, collections.abc.MutableMapping):
            _logger.warning("AnyVar(object_store=) should be a mutable mapping; you're on your own")

        self.data_proxy = data_proxy
        self.object_store = object_store
        self.translator = Translator(
            data_proxy=data_proxy,
            normalize=True,
            identify=True
        )

    def put_object(self, vo):
        v = vr_enref(vo, self.object_store)
        _id = ga4gh_identify(v)
        return _id

    def get_object(self, id, deref=False):
        v = self.object_store[id]
        return vr_deref(v, self.object_store) if deref else v


    def create_text(self, defn):
        vo = models.Text(definition=defn)
        vo._id = ga4gh_identify(vo)
        return vo


if __name__ == "__main__":
    import os
    from biocommons.seqrepo import SeqRepo
    from ga4gh.vr.dataproxy import SeqRepoDataProxy

    seqrepo_dir = os.environ.get("SEQREPO_DIR", "/usr/local/share/seqrepo/latest")
    data_proxy = SeqRepoDataProxy(SeqRepo(root_dir=seqrepo_dir))
    object_store = {}
         
    av = AnyVar(data_proxy=data_proxy, object_store=object_store)
    
    v = av.translate_allele("NM_000551.3:c.1A>T", fmt="hgvs")
    vid = av.put_object(v)

    v2 = av.get_object(vid, deref=True)
    assert v == v2              # roundtrip test
