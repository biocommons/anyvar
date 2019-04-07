"""Runtime globals (really, thread locals)

Items created here are singletons within the thread

"""


from flask import current_app

from vmc.extra.bundlemanager import BundleManager
from .translator import Translator


def _get_g(k, fn):
    """fetch a global singleton, creating with `fn` on first invocation"""
    v = getattr(current_app, k, None)
    if not v:
        v = fn()
        setattr(current_app, k, v)
    return v

def get_bm():
    return _get_g("_vmc_bundlemanager", BundleManager)
    
def get_translator():
    return _get_g("_translator", lambda: Translator(get_bm()))
