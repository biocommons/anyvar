"""Provide minimal class for backend with no persistent storage"""

from typing import Any

from anyvar.restapi.schema import VariationStatisticType

from . import _Storage


class NoObjectStore(dict, _Storage):
    """Storage backend that does not persistently store any data. Should be used for VCF annotation only"""

    def __init__(self) -> None:
        """Initialize DB handler."""

    def __setitem__(self, name: str, value: Any) -> None:  # noqa: ANN401
        """Add item to database if batch mode is off, noop if batch mode is on.

        :param name: value for `vrs_id` field
        :param value: value for `vrs_object` field
        """
        raise NotImplementedError("Not yet implemented")

    def wait_for_writes(self) -> None:
        """Return immediately as no pending database modifications occur in this backend."""

    def close(self) -> None:
        """Return immediately as no pending database connections need closing."""

    def get_variation_count(self, variation_type: VariationStatisticType) -> int:
        """Get total # of registered variations of requested type.

        :param variation_type: variation type to check
        :raise NotImplementedError:
        """
        raise NotImplementedError

    def search_variations(self, refget_accession: str, start: int, stop: int) -> list:
        """Find all alleles that were registered that are in 1 genomic region

        :param refget_accession: refget accession (SQ. identifier)
        :param start: Start genomic region to query
        :param stop: Stop genomic region to query

        :raise NotImplementedError:
        """
        raise NotImplementedError

    def wipe_db(self) -> None:
        """Remove all stored records from the cache"""
        self.clear()
