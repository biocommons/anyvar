"""Runtime globals (really, thread locals)

Items created here are singletons within the thread

"""

import os

from flask import current_app

from ga4gh.vrs.dataproxy import create_dataproxy, _DataProxy

from ..anyvar import AnyVar
from ..storage import create_storage

anyvar_db_fn = os.path.expanduser("/tmp/anyvar.db")



def _get_g(k, fn):
    """fetch a global singleton, creating with `fn` on first invocation"""
    v = getattr(current_app, k, None)
    if not v:
        v = fn()
        setattr(current_app, k, v)
    return v


def get_dataproxy() -> _DataProxy:
    return _get_g("_dataproxy", create_dataproxy)


def _create_anyvar() -> AnyVar:
    """the Manager is really just a bundle of stuff used frequently in the app

    """

    storage = create_storage()       # config: ANYVAR_STORAGE_URI
    data_proxy = get_dataproxy()
    return AnyVar(object_store=storage)

def get_anyvar() -> AnyVar:
    return _get_g("_anyvar", _create_anyvar)
