"""Provide minimal class for backend with no persistent storage"""

from typing import Any

from anyvar.restapi.schema import VariationStatisticType

from . import _Storage


class NoObjectStore(_Storage):
    """"Storage backend that does not store any data. Should be used for VCF annotation only"""

    def __repr__(self) -> str:
        return 'NoObjectStore'

    def __setitem__(self, name: str, value: Any) -> None:  # noqa: ANN401
        raise NotImplementedError

    def __getitem__(self, name: str) -> Any | None:  # noqa: ANN401
        raise NotImplementedError

    def wait_for_writes(self) -> None:
        pass

    def close(self) -> None:
        pass

    def get_variation_count(self, variation_type: VariationStatisticType) -> int:
        raise NotImplementedError

    def search_variations(self, refget_accession: str, start: int, stop: int) -> list:
        raise NotImplementedError

    def wipe_db(self) -> None:
        pass
