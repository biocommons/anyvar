"""Helper functions used by routers"""

from http import HTTPStatus

from fastapi import HTTPException

from anyvar import AnyVar
from anyvar.core import objects
from anyvar.restapi.schema import TranslationResult
from anyvar.translate.base import TranslationError, Translator


def get_vrs_object(
    av: AnyVar,
    vrs_object_id: str,
    object_type: type[objects.SupportedVrsObject] | None = None,
) -> objects.SupportedVrsObject:
    """Get VRS variation given VRS ID

    :param av: AnyVar instance
    :param vrs_object_id: VRS Object ID to retrieve
    :param object_type: (Optional) The type of object to retrieve
    :raises HTTPException: If no VRS object ID found
    :return: VrsObject
    """
    try:
        return av.get_object(vrs_object_id, object_type)
    except KeyError as e:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=f"VRS Object {vrs_object_id} not found",
        ) from e


def translate_variation(
    tlr: Translator,
    definition: str,
    fmt: str | None = None,
    assembly_name: str | None = "GRCh38",
    require_validation: bool = True,
    rle_seq_limit: int | None = 50,
    **kwargs,  # need to keep this for extras in model_dump
) -> TranslationResult:
    """Perform variant translation

    :param tlr: Translator instance
    :param definition: User-provided string describing or referencing a variation.
    :param fmt: The format of ``definition``. If None, will guess the appropriate format.
    :param assembly_name: Assembly name for ``var``.
        Only used when ``var`` uses gnomad format.
        Defaults to "GRCh38".
        VRS-Python sets a default, but we should set a default just in case VRS-Python ever changes the default.
    :param require_validation: Whether validation checks must pass in order to return a
        VRS Allele.
    :param rle_seq_limit: If RLE is set as the new state after normalization, this sets
        the limit for the length of the `sequence`.
        To exclude `sequence` from the response, set to 0.
        For no limit, set to `None`.
    :return: TranslationResult object with translated variation, if translation is
        successful. Otherwise, return error message
    """
    try:
        translated_variation = tlr.translate_variation(
            definition,
            fmt=fmt,
            assembly_name=assembly_name,
            require_validation=require_validation,
            rle_seq_limit=rle_seq_limit,
        )
        return TranslationResult(variation=translated_variation)
    except TranslationError as e:
        return TranslationResult(error=str(e))
