"""Runtime globals (really, thread locals)

Items created here are singletons within the thread

"""

import os
from typing import Any, Callable, Optional

from flask import current_app
from ga4gh.vrs.dataproxy import create_dataproxy, _DataProxy
from anyvar.translate.translate import TranslatorSetupException

from anyvar.translate.variation_normalizer import VariationNormalizerRestTranslator

from ..anyvar import AnyVar
from ..storage import create_storage
from ..translate import _Translator

anyvar_db_fn = os.path.expanduser("/tmp/anyvar.db")


def _get_g(key: str, creator_function: Callable) -> Any:
    """Fetch a global singleton, creating with `fn` on first invocation

    :param key: object key associated with current Flask instance
    :param creator_function: called to create object if it doesn't already exist
    """
    singleton_object = getattr(current_app, key, None)
    if not singleton_object:
        singleton_object = creator_function()
        setattr(current_app, key, singleton_object)
    return singleton_object


def get_dataproxy() -> _DataProxy:
    return _get_g("_dataproxy", create_dataproxy)


def create_translator(uri: Optional[str] = None) -> _Translator:
    """Create variation translator middleware.

    Currently accepts REST interface only.

    :param uri: location listening for REST requests
    :return: instantiated Translator instance
    """

    if not uri:
        uri = os.environ.get("ANYVAR_VARIATION_NORMALIZER_URI")
        if not uri:
            raise TranslatorSetupException(
                "No Translator object or URI provided."
            )
    return VariationNormalizerRestTranslator(uri)


def get_translator() -> _Translator:
    return _get_g("_translator", create_translator)


def _create_anyvar() -> AnyVar:
    """the Manager is really just a bundle of stuff used frequently in the app

    """

    storage = create_storage()       # config: ANYVAR_STORAGE_URI
    translator = get_translator()
    return AnyVar(object_store=storage, translator=translator)

def get_anyvar() -> AnyVar:
    return _get_g("_anyvar", _create_anyvar)
