"""Runtime globals (really, thread locals)

Items created here are singletons within the thread

"""

import os

from flask import current_app

from biocommons.seqrepo import SeqRepo
from ga4gh.vr.dataproxy import SeqRepoDataProxy

from .manager import Manager
from .storage import AnyVarStorage


anyvar_db_fn = os.path.expanduser("/tmp/anyvar")


def _get_g(k, fn):
    """fetch a global singleton, creating with `fn` on first invocation"""
    v = getattr(current_app, k, None)
    if not v:
        v = fn()
        setattr(current_app, k, v)
    return v

def _create_Manager():
    """the Manager is really just a bundle of stuff used frequently in the app

    """
    storage = AnyVarStorage(anyvar_db_fn)
    seqrepo_dir = os.environ.get("SEQREPO_DIR", "/usr/local/share/seqrepo/latest")
    dataproxy = SeqRepoDataProxy(SeqRepo(seqrepo_dir))
    return Manager(storage=storage, dataproxy=dataproxy)

def get_manager():
    return _get_g("_vr_manager", _create_Manager)
