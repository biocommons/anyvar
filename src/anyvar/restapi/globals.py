"""Runtime globals (really, thread locals)

Items created here are singletons within the thread

"""

import os

from flask import current_app

from biocommons.seqrepo import SeqRepo
from ga4gh.vr.dataproxy import SeqRepoDataProxy

from ..anyvar import AnyVar
from ..storage.shelf import ShelfStorage

anyvar_db_fn = os.path.expanduser("/tmp/anyvar.db")


def _get_g(k, fn):
    """fetch a global singleton, creating with `fn` on first invocation"""
    v = getattr(current_app, k, None)
    if not v:
        v = fn()
        setattr(current_app, k, v)
    return v


def _create_anyvar():
    """the Manager is really just a bundle of stuff used frequently in the app

    """
    storage = ShelfStorage(anyvar_db_fn)
    seqrepo_dir = os.environ.get("SEQREPO_DIR", "/usr/local/share/seqrepo/latest")
    data_proxy = SeqRepoDataProxy(SeqRepo(seqrepo_dir))
    return AnyVar(object_store=storage, data_proxy=data_proxy)


def get_anyvar():
    return _get_g("_anyvar", _create_anyvar)
