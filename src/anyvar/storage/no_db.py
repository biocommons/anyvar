"""Provide minimal class for backend with no persistent storage"""

from typing import Any

from anyvar.restapi.schema import VariationStatisticType

from . import _BatchManager, _Storage


class NoObjectStore(dict, _Storage):
    """Storage backend that does not persistently store any data. Should be used for VCF annotation only"""

    def __init__(self) -> None:
        """Initialize DB handler."""
        super().__init__()
        self.batch_manager = NoStorageBatchManager
        self.batch_mode = False

    def __setitem__(self, name: str, value: Any) -> None:  # noqa: ANN401
        """Add item to database if batch mode is off, noop if batch mode is on.

        :param name: value for `vrs_id` field
        :param value: value for `vrs_object` field
        """
        if not self.batch_mode:
            super().__setitem__(name, value)

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


class NoStorageBatchManager(_BatchManager):
    """Context manager disabling any insertions for bulk insertion statements

    Use in cases like VCF ingest when intaking large amounts of data at once.
    Prevents the backing in-memory dictionary used for enref/deref for single VRS IDs to be used during bulk operations
    """

    def __init__(self, storage: NoObjectStore) -> None:
        """Initialize context manager.

        :param storage: NoObjectStore instance to manage
        :raise ValueError: if `storage` param is not a `NoObjectStore` instance
        """
        if not isinstance(storage, NoObjectStore):
            msg = "NoStorageBatchManager requires a NoObjectStore instance"
            raise TypeError(msg)
        self._storage = storage

    def __enter__(self) -> None:
        """Enter managed context."""
        self._storage.batch_mode = True

    def __exit__(
        self,
        exc_type: type | None,
        exc_value: BaseException | None,
        traceback: Any | None,  # noqa: ANN401
    ) -> bool:
        """Handle exit from context management.  Hands off final batch to background bulk insert processor.

        :param exc_type: type of exception encountered, if any
        :param exc_value: exception value
        :param traceback: traceback for context of exception
        :return: True if no exceptions encountered, False otherwise
        """
        self._storage.batch_mode = False
        return not exc_type
