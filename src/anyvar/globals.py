"""Runtime globals (really, thread locals)

Items created here are singletons within the thread

"""

import os

from flask import current_app

from .manager import Manager
from .storage import AnyVarStorage


anyvar_db_fn = os.path.expanduser("~/tmp/anyvar")


def _get_g(k, fn):
    """fetch a global singleton, creating with `fn` on first invocation"""
    v = getattr(current_app, k, None)
    if not v:
        v = fn()
        setattr(current_app, k, v)
    return v

def _create_Manager():
    storage = AnyVarStorage(anyvar_db_fn)
    return Manager(storage=storage)

def get_manager():
    return _get_g("_vmc_manager", _create_Manager)
    
