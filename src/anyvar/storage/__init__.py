DEFAULT_STORAGE_URI = "postgresql://postgres@localhost:5432/anyvar"

from abc import abstractmethod
from collections.abc import MutableMapping
from contextlib import AbstractContextManager

from anyvar.restapi.schema import VariationStatisticType


class _Storage(MutableMapping):
    """Define base storage backend class."""

    batch_manager = None

    @abstractmethod
    def search_variations(self, refget_accession: str, start: int, stop: int):
        """Find all registered variations in a provided genomic region

        :param refget_accession: refget accession (SQ. identifier)
        :param start: Start genomic region to query
        :param stop: Stop genomic region to query

        :return: A list of VRS Alleles that have locations referenced as identifiers
        """

    @abstractmethod
    def get_variation_count(self, variation_type: VariationStatisticType) -> int:
        """Get total # of registered variations of requested type.

        :param variation_type: variation type to check
        :return: total count
        """

    @abstractmethod
    def wipe_db(self):
        """Empty database of all stored records."""

    @abstractmethod
    def wait_for_writes(self):
        """Returns once any currently pending database modifications have been completed."""

    @abstractmethod
    def close(self):
        """Closes the storage integration and cleans up any resources"""


class _BatchManager(AbstractContextManager):
    """Base context management class for batch writing.

    Theoretically we could write batch methods without a context manager -- some DB
    implementations have them natively -- but this makes it easier for us to ensure
    transactions are properly handled.
    """

    @abstractmethod
    def __init__(self, storage: _Storage):
        """Initialize context manager.

        :param storage: Storage instance to manage. Should be taken from the active
        AnyVar instance -- otherwise it won't be able to delay insertions.
        """
