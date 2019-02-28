"""Runtime globals (really, thread locals)

Items here are effectively singletons within the thread

"""

from vmc.extra.bundlemanager import BundleManager

from .translator import Translator


bm = BundleManager()
translator = Translator()




