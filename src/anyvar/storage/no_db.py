"""Provide minimal class for backend with no persistent storage"""
from typing import Any

from . import _BatchManager, _Storage


class NoObjectStore(dict, _Storage):
    """"Storage backend that does not persistently store any data. Should be used for VCF annotation only"""

    def __init__(self) -> None:
        super().__init__()
        self.batch_manager = NoStorageBatchManager
        self.batch_mode = False

    def __setitem__(self, name: str, value: Any) -> None:  # noqa: ANN401
        if not self.batch_mode:
            super().__setitem__(name, value)

    def wait_for_writes(self) -> None:
        pass

    def close(self) -> None:
        pass

    def get_variation_count(self, variation_type: Any) -> int:
        raise NotImplementedError

    def search_variations(self, refget_accession: str, start: int, stop: int) -> list:
        raise NotImplementedError

    def wipe_db(self) -> None:
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
            raise ValueError(msg)
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
        return True if exc_type is None else False
