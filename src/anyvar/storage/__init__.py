DEFAULT_STORAGE_URI = "memory:"

from abc import abstractmethod
from collections.abc import MutableMapping

from anyvar.restapi.schema import VariationStatisticType


class _Storage(MutableMapping):
    """Define base storage backend class."""

    @abstractmethod
    def search_variations(self, ga4gh_accession_id: str, start: int, stop: int):
        """Find all registered variations in a provided genomic region

        :param ga4gh_accession_id: ga4gh accession for sequence identifier
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
