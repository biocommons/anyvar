import json
import os
from collections.abc import Iterable
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from ga4gh.vrs import models

from anyvar.anyvar import AnyVar, create_storage, create_translator
from anyvar.restapi.main import app as anyvar_restapi
from anyvar.storage.base_storage import DataIntegrityError, Storage, StoredObjectType
from anyvar.utils import types
from anyvar.utils.funcs import build_vrs_variant_from_dict

pytest_plugins = ("celery.contrib.pytest",)


def pytest_collection_modifyitems(items):
    """Modify test items in place to ensure test modules run in a given order."""
    module_order = [
        "test_lifespan",
        "test_variation",
        "test_general",
        "test_location",
        "test_search",
        "test_annotate_vcf",
        "test_ingest_vcf",
        "test_storage_implementation",
        "test_no_db",
        "test_liftover",
    ]
    # remember to add new test modules to the order constant:
    assert len(module_order) == len(list(Path(__file__).parent.rglob("test_*.py")))
    items.sort(key=lambda i: module_order.index(i.module.__name__))


@pytest.fixture(scope="session", autouse=True)
def storage():
    """Provide API client instance as test fixture"""
    if "ANYVAR_TEST_STORAGE_URI" in os.environ:
        storage_uri = os.environ["ANYVAR_TEST_STORAGE_URI"]
    else:
        storage_uri = "postgresql://postgres:postgres@localhost:5432/anyvar_test"

    storage = create_storage(uri=storage_uri)
    storage.wipe_db()
    return storage


@pytest.fixture(scope="session")
def client(storage):
    translator = create_translator()
    anyvar_restapi.state.anyvar = AnyVar(object_store=storage, translator=translator)
    return TestClient(app=anyvar_restapi)


@pytest.fixture(scope="session")
def test_data_dir() -> Path:
    """Provide Path instance pointing to test data directory"""
    return Path(__file__).parent / "data"


@pytest.fixture(scope="session")
def alleles(test_data_dir) -> dict:
    """Provide allele fixture object."""
    with (test_data_dir / "variations.json").open() as f:
        return json.load(f)["alleles"]


@pytest.fixture(scope="session")
def preloaded_alleles(storage, alleles):
    """Preload alleles into the database for tests that need them."""
    storage.add_objects(
        [
            build_vrs_variant_from_dict(a["allele_response"]["object"])
            for a in alleles.values()
        ]
    )
    return alleles


@pytest.fixture(scope="session")
def celery_config():
    return {
        "broker_url": os.environ.get("CELERY_BROKER_URL", "redis://"),
        "result_backend": os.environ.get("CELERY_BACKEND_URL", "redis://"),
        "task_default_queue": "anyvar_q",
        "event_queue_prefix": "anyvar_ev",
        "task_serializer": "json",
        "result_serializer": "json",
        "accept_content": ["application/json"],
    }


class TemporaryStorage(Storage):
    """Abstract base class for interacting with storage backends."""

    def __init__(self, db_url: str | None = None) -> None:
        """Initialize the storage backend.

        :param db_url: Database connection URL
        """
        self.wipe_db()

    def close(self) -> None:
        """Close the storage backend."""

    def wait_for_writes(self) -> None:
        """Wait for all background writes to complete.

        NOTE: This is a no-op for synchronous storage backends.
        """

    def wipe_db(self) -> None:
        """Wipe all data from the storage backend."""
        self.alleles: dict[str, models.Allele] = {}
        self.sequence_locations: dict[str, models.SequenceLocation] = {}
        self.sequence_references: dict[str, models.SequenceReference] = {}
        self.mappings: list[types.VariationMapping] = []
        self.annotations: list[types.Annotation] = []

    def add_objects(self, objects: Iterable[types.VrsObject]) -> None:
        """Add multiple VRS objects to storage.

        If an object ID conflicts with an existing object, skip it.

        This method assumes that for VRS objects (e.g. `Allele`, `SequenceLocation`,
        `SequenceReference`) the `.id` property is present and uses the correct
        GA4GH identifier for that object

        :param objects: VRS objects to add to storage
        """
        for o in objects:
            if isinstance(o, models.Allele) and o.id not in self.alleles:
                self.alleles[o.id] = o
            elif (
                isinstance(o, models.SequenceLocation)
                and o.id not in self.sequence_locations
            ):
                self.sequence_locations[o.id] = o
            elif (
                isinstance(o, models.SequenceReference)
                and o.id not in self.sequence_references
            ):
                self.sequence_references[o.id] = o
            else:
                raise NotImplementedError

    def _get_object_collection(self, object_type: StoredObjectType) -> dict:
        if object_type == StoredObjectType.ALLELE:
            return self.alleles
        if object_type == StoredObjectType.SEQUENCE_LOCATION:
            return self.sequence_locations
        if object_type == StoredObjectType.SEQUENCE_REFERENCE:
            return self.sequence_references
        else:
            raise ValueError

    def get_objects(
        self, object_type: StoredObjectType, object_ids: Iterable[str]
    ) -> Iterable[types.VrsObject]:
        """Retrieve multiple VRS objects from storage by their IDs.

        If no object matches a given ID, that ID is skipped

        :param object_type: type of object to get
        :param object_ids: IDs of objects to fetch
        :return: iterable collection of VRS objects matching given IDs
        """
        object_collection = self._get_object_collection(object_type)
        return [v for k, v in object_collection.items() if k in object_ids]

    def get_all_object_ids(self) -> Iterable[str]:
        """Retrieve all object IDs from storage.

        :return: all stored VRS object IDs
        """
        return (
            self.alleles.keys()
            | self.sequence_locations.keys()
            | self.sequence_references.keys()
        )

    def _is_safe_to_delete(self, object_type: StoredObjectType, object_id: str) -> bool:
        raise NotImplementedError

    def delete_objects(
        self, object_type: StoredObjectType, object_ids: Iterable[str]
    ) -> None:
        """Delete all objects of a specific type from storage.

        If no object matching a given ID is found, it's ignored.

        :param object_type: type of objects to delete
        :param object_ids: IDs of objects to delete
        :raise DataIntegrityError: if attempting to delete an object which is
            depended upon by another object
        """
        for object_id in object_ids:
            if not self._is_safe_to_delete(object_type, object_id):
                raise DataIntegrityError
        if isinstance(object_type.)
        object_collection
        for
        if not self._is_safe_to_delete()

    def add_mapping(self, mapping: types.VariationMapping) -> None:
        """Add a mapping between two objects.

        If the mapping instance already exists, do nothing.

        :param mapping: mapping object
        :raise KeyError: if source or destination IDs aren't present in DB
        """

    def delete_mapping(self, mapping: types.VariationMapping) -> None:
        """Delete a mapping between two objects.

        If no such mapping exists in the DB, does nothing.

        :param mapping: mapping object
        :raise DataIntegrityError: if attempting to delete an object which is
            depended upon by another object
        """

    def get_mappings(
        self,
        source_object_id: str,
        mapping_type: types.VariationMappingType | None,
    ) -> Iterable[types.VariationMapping]:
        """Return an iterable of mappings from the source ID of the given mapping type.

        :param source_object_id: ID of the source object
        :param mapping_type: The type of mapping to retrieve (defaults to `None` to
            retrieve all mappings for the source ID)
        :return: iterable collection of mapping descriptors (empty if no matching mappings exist)
        """

    def search_alleles(
        self,
        refget_accession: str,
        start: int,
        stop: int,
    ) -> list[vrs_models.Allele]:
        """Find all Alleles in the particular region

        :param refget_accession: refget accession (SQ. identifier)
        :param start: Start genomic region to query
        :param stop: Stop genomic region to query

        :return: a list of Alleles
        """

    def add_annotation(self, annotation: types.Annotation) -> None:
        """Adds an annotation to the database.

        :param annotation: The annotation to add
        :return: The ID of the newly-added annotation
        """

    def get_annotations_by_object_and_type(
        self, object_id: str, annotation_type: str | None = None
    ) -> list[types.Annotation]:
        """Get all annotations for the specified object, optionally filtered by type.

        :param object_id: The ID of the object to retrieve annotations for
        :param annotation_type: The type of annotation to retrieve (defaults to `None` to retrieve all annotations for the object)
        :return: A list of annotations
        """

    def delete_annotation(self, annotation: types.Annotation) -> None:
        """Deletes an annotation from the database

        If no such annotation exists, do nothing.

        :param annotation: The annotation object to delete
        :raise DataIntegrityError: if attempting to delete an object which is
            depended upon by another object
        """
