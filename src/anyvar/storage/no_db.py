"""Provide minimal class for backend with no persistent storage"""

from anyvar.restapi.schema import VariationStatisticType

from . import _Storage


class NoObjectStore(dict, _Storage):
    """"Storage backend that does not persistently store any data. Should be used for VCF annotation only"""

    def wait_for_writes(self) -> None:
        pass

    def close(self) -> None:
        pass

    def get_variation_count(self, variation_type: VariationStatisticType) -> int:
        raise NotImplementedError

    def search_variations(self, refget_accession: str, start: int, stop: int) -> list:
        raise NotImplementedError

    def wipe_db(self) -> None:
        self.clear()
