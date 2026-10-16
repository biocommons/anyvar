"""Provide API routes related to categorical variants"""

import contextlib
from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Body, HTTPException, Path, Query, Request
from ga4gh.vrs import models as vrs

from anyvar.anyvar import AnyVar, InvalidCategoricalVariantError
from anyvar.core.categorical_variants import CanonicalAllele, ProteinSequenceConsequence
from anyvar.mapping import liftover
from anyvar.mapping.protocols import project_and_register_variations
from anyvar.restapi.examples import (
    CANONICAL_ALLELE_EXAMPLE,
    CANONICAL_ALLELE_ID_EXAMPLES,
    CANONICAL_ALLELE_OPENAPI_EXAMPLES,
    CATEGORICAL_VARIANT_MEMBER_EXAMPLES,
    PROTEIN_SEQUENCE_CONSEQUENCE_EXAMPLE,
    PROTEIN_SEQUENCE_CONSEQUENCE_ID_EXAMPLES,
    PROTEIN_SEQUENCE_CONSEQUENCE_OPENAPI_EXAMPLES,
)
from anyvar.restapi.schema import VariationRequest
from anyvar.restapi.variation_request import (
    handle_translation_request,
    variation_request_body,
)
from anyvar.restapi.vrs_objects import get_vrs_object

catvar_router = APIRouter()

_put_psq_example = PROTEIN_SEQUENCE_CONSEQUENCE_EXAMPLE
_put_ca_example = CANONICAL_ALLELE_EXAMPLE

_put_psq_description = """Register a Protein Sequence Consequence Categorical Variant.

AnyVar expects the following:

* The provided object must be a valid Categorical Variant, per the Cat-VRS specification
* It must contain a single constraint, which is a Defining Allele Constraint
* The defining allele must be defined on a protein sequence
* The Categorical Variant ID should be a reference to an external knowledgebase record

AnyVar interprets this categorical variant as encompassing all variants that resolve to the provided defining allele through any combination of reference sequence liftover and transcript or protein projection.
"""

_put_psq_body = Body(
    description="A protein sequence consequence categorical variant with an ID that references an external knowledgebase record.",
    openapi_examples=PROTEIN_SEQUENCE_CONSEQUENCE_OPENAPI_EXAMPLES,
)


@catvar_router.put(
    "/protein_sequence_consequences",
    response_model_exclude_none=True,
    operation_id="put_psq",
    summary="Register a protein sequence consequence categorical variant",
    description=_put_psq_description,
)
def put_psq(
    request: Request,
    catvar: Annotated[ProteinSequenceConsequence, _put_psq_body],
) -> None:
    """Register a protein sequence consequence catvar"""
    av: AnyVar = request.app.state.anyvar
    try:
        av.register_psq_catvar(catvar)
    except InvalidCategoricalVariantError as e:
        raise HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            detail="Validation checks failed -- see description for data requirements",
        ) from e


@catvar_router.get(
    "/protein_sequence_consequences/{psq_id}", response_model_exclude_none=True
)
def get_protein_sequence_consequence(
    request: Request,
    psq_id: Annotated[
        str,
        Path(
            description="Identifier of a registered protein sequence consequence.",
            openapi_examples=PROTEIN_SEQUENCE_CONSEQUENCE_ID_EXAMPLES,
        ),
    ],
) -> ProteinSequenceConsequence:
    """Fetch a Canonical Allele Categorical Variant by ID"""
    av: AnyVar = request.app.state.anyvar
    psq = av.get_psq_catvar(psq_id)
    if not psq:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND)
    return psq


_put_ca_body = Body(
    description="A canonical allele categorical variant with an ID that references an external knowledgebase record.",
    openapi_examples=CANONICAL_ALLELE_OPENAPI_EXAMPLES,
)

_put_ca_description = """Register a Canonical Allele Categorical Variant.

AnyVar expects the following:

* The provided object must be a valid Categorical Variant, per the Cat-VRS specification
* It must contain a single constraint, which is a Defining Allele Constraint
* The defining allele must be defined on a genomic sequence
* The Categorical Variant ID should be a reference to an external knowledgebase record

AnyVar interprets this categorical variant as encompassing all variants that the defining allele may resolve to via any combination of reference sequence liftover and transcription.
"""


@catvar_router.put(
    "/canonical_alleles",
    response_model_exclude_none=True,
    operation_id="put_canonical_allele",
    summary="Register a canonical allele categorical variant",
    description=_put_ca_description,
)
def put_canonical_allele(
    request: Request, catvar: Annotated[CanonicalAllele, _put_ca_body]
) -> None:
    """Register a canonical allele catvar"""
    av: AnyVar = request.app.state.anyvar
    try:
        av.register_ca_catvar(catvar)
    except InvalidCategoricalVariantError as e:
        raise HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            detail="Validation checks failed -- see description for data requirements",
        ) from e
    allele = catvar.constraints[0].root.allele
    if av.projector:
        project_and_register_variations(av.projector, av.object_store, allele)
    try:
        lo_allele = liftover.liftover_and_register_variant(
            allele, av.object_store, av.translator.dp
        )
    except liftover.LiftoverError:
        pass
    else:
        if av.projector:
            # add projections for liftover result if successful
            project_and_register_variations(av.projector, av.object_store, lo_allele)


@catvar_router.get("/canonical_alleles/{ca_id}", response_model_exclude_none=True)
def get_canonical_allele(
    request: Request,
    ca_id: Annotated[
        str,
        Path(
            description="Identifier of a registered canonical allele.",
            openapi_examples=CANONICAL_ALLELE_ID_EXAMPLES,
        ),
    ],
) -> CanonicalAllele:
    """Fetch a Canonical Allele Categorical Variant by ID"""
    av: AnyVar = request.app.state.anyvar
    ca = av.get_ca_catvar(ca_id)
    if not ca:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND)
    return ca


@catvar_router.get(
    "",
    response_model_exclude_none=True,
    operation_id="get_catvars_by_member_id",
    summary="Retrieve categorical variants by member VRS object ID",
    description=(
        "Retrieve registered categorical variants that include the provided VRS "
        "object ID as a member. The ID must already resolve to a registered VRS "
        "object; this endpoint does not translate expressions or create new mappings."
    ),
)
def get_catvars_by_member_id(
    request: Request,
    vrs_id: Annotated[
        str,
        Query(
            description=(
                "Identifier for a registered VRS object to use as the categorical "
                "variant member lookup target."
            ),
            openapi_examples=CATEGORICAL_VARIANT_MEMBER_EXAMPLES,
        ),
    ],
) -> list[CanonicalAllele | ProteinSequenceConsequence]:
    """Retrieve categorical variants containing a registered VRS object."""
    av: AnyVar = request.app.state.anyvar
    vrs_object = get_vrs_object(av, vrs_id, object_type=vrs.Allele)
    if not isinstance(vrs_object, vrs.Allele):
        raise TypeError
    vrs_ids = {vrs_object.id}
    with contextlib.suppress(liftover.LiftoverError):
        lo_allele = liftover.liftover_variant(vrs_object)
        vrs_ids.add(lo_allele.id)
    # don't need to do projection here -- they would've already been done at registration time
    catvars = av.object_store.get_catvars_by_allele_ids(list(vrs_ids))
    return catvars


@catvar_router.post(
    "",
    response_model_exclude_none=True,
    operation_id="get_catvars_by_expression",
    summary="Retrieve categorical variants by variant expression",
    description=(
        "Translate a submitted variant expression into a VRS object, then retrieve "
        "registered categorical variants that include that object, or equivalent "
        "mapped objects, as members. This endpoint may compute mappings needed for "
        "lookup, but does not register the submitted variation or persist newly "
        "computed mappings."
    ),
)
def get_catvars_by_variation(
    request: Request,
    variation: Annotated[VariationRequest, variation_request_body],
) -> list[CanonicalAllele | ProteinSequenceConsequence]:
    """Retrieve categorical variants matching a translated variation expression."""
    av: AnyVar = request.app.state.anyvar
    translated_variation = handle_translation_request(av.translator, variation)
    allele_ids = {translated_variation.id}
    with contextlib.suppress(liftover.LiftoverError):
        lo_allele = liftover.liftover_variant(translated_variation)
        allele_ids.add(lo_allele.id)
    if av.projector:
        projections = av.projector.project_variations(translated_variation)
        allele_ids |= {p.destination_variation.id for p in projections.projections}
    catvars = av.object_store.get_catvars_by_allele_ids(list(allele_ids))
    return catvars
