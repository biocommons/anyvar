"""Provide PostgreSQL-based storage implementation."""

import base64
import json
from abc import ABC, abstractmethod
from collections.abc import Iterable
from dataclasses import dataclass

from ga4gh.vrs import models as vrs_models

from anyvar.core import metadata
from anyvar.core import objects as anyvar_objects


class StorageError(Exception):
    """Base AnyVar storage error."""


class DataIntegrityError(StorageError):
    """Raise for attempts to delete objects depended upon by other objects"""


class MissingVariationReferenceError(StorageError):
    """Raise for attempts to insert an annotation or mapping that references a non-existent variation"""


class IncompleteVrsObjectError(StorageError):
    """Raise if provided VRS object is missing fully-materialized properties required for storage"""


class InvalidSearchParamsError(StorageError):
    """Raise if search params violate specified logical constraints"""


@dataclass(frozen=True)
class AlleleSearchPage:
    """Return object for implementing keyset pagination in allele search

    Used in accordance with GA4GH pagination guidelines --
    https://github.com/ga4gh/TASC/blob/main/recommendations/API%20pagination%20guide.md#token-based-pagination
    """

    items: list[vrs_models.Allele]
    next_cursor: str | None


class Storage(ABC):
    """Abstract base class for interacting with storage backends."""

    @abstractmethod
    def __init__(self, *args, **kwargs) -> None:
        """Initialize the storage backend."""

    @abstractmethod
    def close(self) -> None:
        """Close the storage backend."""

    @abstractmethod
    def wait_for_writes(self) -> None:
        """Wait for all background writes to complete.

        NOTE: This is a no-op for synchronous storage backends.
        """

    @abstractmethod
    def wipe_db(self) -> None:
        """Wipe all data from the storage backend."""

    @abstractmethod
    def add_objects(self, objects: Iterable[anyvar_objects.VrsObject]) -> None:
        """Add multiple VRS objects to storage.

        If an object ID conflicts with an existing object, skip it.

        This method assumes that for VRS objects (e.g. `Allele`, `SequenceLocation`,
        `SequenceReference`) the `.id` property is present and uses the correct
        GA4GH identifier for that object. It also assumes that contained objects are
        similarly properly identified and materialized in full, not just as an IRI reference.
        An error is raised if these assumptions are violated, rolling back the entire
        transaction.

        :param objects: VRS objects to add to storage
        :raise IncompleteVrsObjectError: if object is missing required properties or if
            required properties aren't fully dereferenced
        """

    @abstractmethod
    def get_objects(
        self, object_type: type[anyvar_objects.VrsObject], object_ids: Iterable[str]
    ) -> Iterable[anyvar_objects.VrsObject]:
        """Retrieve multiple VRS objects from storage by their IDs.

        If no object matches a given ID, that ID is skipped

        :param object_type: type of object to get
        :param object_ids: IDs of objects to fetch
        :return: iterable collection of VRS objects matching given IDs
        """

    @abstractmethod
    def delete_objects(
        self, object_type: type[anyvar_objects.VrsObject], object_ids: Iterable[str]
    ) -> None:
        """Delete all objects of a specific type from storage.

        * If no object matching a given ID is found, it's ignored.
        * Deletes do not cascade.

        :param object_type: type of objects to delete
        :param object_ids: IDs of objects to delete
        :raise DataIntegrityError: if attempting to delete an object which is
            depended upon by another object
        """

    @abstractmethod
    def add_mapping(self, mapping: metadata.VariationMapping) -> None:
        """Add a mapping between two objects.

        If the mapping instance already exists, do nothing.

        :param mapping: mapping object
        :raise MissingVariationReferenceError: if source or destination IDs aren't present in DB
        """

    @abstractmethod
    def delete_mapping(self, mapping: metadata.VariationMapping) -> None:
        """Delete a mapping between two objects.

        * If no such mapping exists in the DB, does nothing.
        * Deletes do not cascade.

        :param mapping: mapping object
        :raise DataIntegrityError: if attempting to delete an object which is
            depended upon by another object
        """

    @abstractmethod
    def get_mappings(
        self,
        object_id: str,
        as_source: bool,
        mapping_type: metadata.VariationMappingType | None = None,
    ) -> Iterable[metadata.VariationMapping]:
        """Return an iterable of mappings

        Optionally provide a type to filter results.

        :param object_id: ID of object to get mappings for
        :param as_source: If ``True``, object_id is treated as the source. If ``False``,
            ``object_id`` is treated as the destination.
        :param mapping_type: The type of mapping to retrieve (defaults to `None` to
            retrieve all mappings for the source ID)
        :return: iterable collection of mapping descriptors (empty if no matching mappings exist)
        """

    @abstractmethod
    def add_annotation(self, annotation: metadata.Annotation) -> None:
        """Adds an annotation to the database.

        Adding the same annotation repeatedly creates redundant records.

        :param annotation: The annotation to add
        :raise MissingVariationReferenceError: if no object corresponding to the annotation's object ID is present in DB
        """

    @abstractmethod
    def get_annotations(
        self, object_id: str, annotation_type: str | None = None
    ) -> list[metadata.Annotation]:
        """Get all annotations for the specified object, optionally filtered by type.

        :param object_id: The ID of the object to retrieve annotations for
        :param annotation_type: The type of annotation to retrieve (defaults to `None` to retrieve all annotations for the object)
        :return: A list of annotations
        """

    @abstractmethod
    def delete_annotation(self, annotation: metadata.Annotation) -> None:
        """Deletes an annotation from the database

        * If no such annotation exists, do nothing.
        * Deletes do not cascade.

        :param annotation: The annotation object to delete
        :raise DataIntegrityError: if attempting to delete an object which is
            depended upon by another object
        """

    @staticmethod
    def _encode_search_cursor(start: int, allele_id: str) -> str:
        """Create cursor for search

        :param start: start value for next row
        :param allele_id: ID for next row
        :return: cursor to use to fetch next page
        """
        raw = json.dumps(
            {"start": start, "id": allele_id}, separators=(",", ":")
        ).encode()
        return base64.urlsafe_b64encode(raw).decode()

    @staticmethod
    def _decode_search_cursor(cursor: str) -> tuple[int, str]:
        """Decode cursor for getting next page during search

        :param cursor: opaque key included with previous result
        :return: start and ID values indicating the first row of the next page
        """
        raw = base64.urlsafe_b64decode(cursor.encode())
        obj = json.loads(raw)
        return int(obj["start"]), str(obj["id"])

    @abstractmethod
    def search_alleles(
        self,
        refget_accession: str,
        start: int,
        stop: int,
        page_size: int = 1000,
        cursor: str | None = None,
    ) -> AlleleSearchPage:
        """Find all Alleles that are located within the specified interval.

        The interval is the closed range [start, stop] on the sequence identified by
        the RefGet SequenceReference accession (`SQ.*`). Both `start` and `stop` are
        inclusive and represent inter-residue positions.

        Uses keyset pagination, meaning that altering the page size while looping through
        successive cursors will effectively nullify the search loop.

        Currently, any variation which overlaps the queried region is returned.

        Todo (see Issue #338):
        * define alternate match modes (partial/full overlap/contained/etc)
        * define behavior for LSE indels and for alternative types of state (RLEs)

        Raises an error if
        * `start` or `end` are negative
        * `end` > `start`

        :param refget_accession: refget accession (e.g. `"SQ.IW78mgV5Cqf6M24hy52hPjyyo5tCCd86"`)
        :param start: Inclusive, inter-residue start position of the interval
        :param stop: Inclusive, inter-residue end position of the interval
        :param page_size: Max # of results to return
        :param cursor: Opaque key indicating start location for query in pagination
        :return: Results page including variants and a cursor for next result page, if available
        :raise InvalidSearchParamsError: if above search param requirements are violated
        """
