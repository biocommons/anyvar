"""Runtime globals (really, thread locals)

Items created here are singletons within the thread

"""


from flask import current_app

from vmc.extra.bundlemanager import BundleManager
from .translator import Translator

from .manager import Manager

import hgvs.parser


def _get_g(k, fn):
    """fetch a global singleton, creating with `fn` on first invocation"""
    v = getattr(current_app, k, None)
    if not v:
        v = fn()
        setattr(current_app, k, v)
    return v

def get_hgvs_parser():
    return get_vmc_manager().hgvs_parser
    
def get_vmc_manager():
    return _get_g("_vmc_manager", lambda: Manager())
    
