from anyvar.restapi.schema import VariationStatisticType

from . import _Storage


class InMemoryStore(dict, _Storage):

    def search_variations(self, ga4gh_accession_id: str, start: int, stop: int):
        raise NotImplementedError

    def get_variation_count(self, variation_type: VariationStatisticType) -> int:
        raise NotImplementedError