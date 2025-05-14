"""Provide tools for and implementations of AnyVar storage backends."""

DEFAULT_STORAGE_URI = "postgresql://postgres@localhost:5432/anyvar"

from abc import abstractmethod
from collections.abc import MutableMapping
from contextlib import AbstractContextManager

from anyvar.restapi.schema import VariationStatisticType


class _Storage(MutableMapping):
    """Define base storage backend class."""

    batch_manager = None

    @abstractmethod
    def wipe_db(self) -> None:
        """Empty database of all stored records."""

    @abstractmethod
    def wait_for_writes(self) -> None:
        """Return once any currently pending database modifications have been completed."""

    @abstractmethod
    def close(self) -> None:
        """Close the storage integration and cleans up any resources"""


class _BatchManager(AbstractContextManager):
    """Base context management class for batch writing.

    Theoretically we could write batch methods without a context manager -- some DB
    implementations have them natively -- but this makes it easier for us to ensure
    transactions are properly handled.
    """

    @abstractmethod
    def __init__(self, storage: _Storage) -> None:
        """Initialize context manager.

        :param storage: Storage instance to manage. Should be taken from the active
        AnyVar instance -- otherwise it won't be able to delay insertions.
        """
