"""Runtime globals (really, thread locals)

Items here are effectively singletons within the thread

"""

from .translator import Translator

translator = Translator()

