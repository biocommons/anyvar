"""Provide API routes related to categorical variants"""

from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Body, HTTPException, Request
from ga4gh.cat_vrs import models as cat_vrs
from ga4gh.vrs import models as vrs

from anyvar.anyvar import AnyVar, InvalidCategoricalVariantError
from anyvar.core.categorical_variants import CanonicalAllele, ProteinSequenceConsequence

catvar_router = APIRouter()

_put_psq_description = """Register a Protein Sequence Consequence Categorical Variant.

AnyVar expects the following:

* The provided object must be a valid Categorical Variant, per the Cat-VRS specification
* It must contain a single constraint, which is a Defining Allele Constraint
* The defining allele must be defined on a protein sequence
* The Categorical Variant ID should be a reference to an external knowledgebase record

AnyVar interprets this categorical variant as encompassing all variants that resolve to the provided defining allele through any combination of reference sequence liftover and transcript or protein projection.
"""

_put_psq_example = cat_vrs.CategoricalVariant(
    id="civic.mpid:12",
    name="BRAF V600E",
    constraints=[
        cat_vrs.Constraint(
            root=cat_vrs.DefiningAlleleConstraint(
                allele=vrs.Allele(
                    id="ga4gh:VA.j4XnsLZcdzDIYa5pvvXM7t1wn9OITr0L",
                    digest="j4XnsLZcdzDIYa5pvvXM7t1wn9OITr0L",
                    location=vrs.SequenceLocation(
                        id="ga4gh:SL.t-3DrWALhgLdXHsupI-e-M00aL3HgK3y",
                        digest="t-3DrWALhgLdXHsupI-e-M00aL3HgK3y",
                        sequenceReference=vrs.SequenceReference(
                            refgetAccession="SQ.cQvw4UsHHRRlogxbWCB8W-mKD4AraM9y",
                        ),
                        start=599,
                        end=600,
                    ),
                    state=vrs.LiteralSequenceExpression(
                        sequence=vrs.sequenceString("E"),
                    ),
                )
            )
        )
    ],
)

_put_psq_body = Body(
    description="A protein sequence consequence categorical variant with an ID that references an external knowledgebase record.",
    example=_put_psq_example,
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
    request: Request, psq_id: str
) -> ProteinSequenceConsequence:
    """Fetch a Canonical Allele Categorical Variant by ID"""
    av: AnyVar = request.app.state.anyvar
    psq = av.get_psq_catvar(psq_id)
    if not psq:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND)
    return psq


_put_ca_example = cat_vrs.CategoricalVariant(
    id="clingen.allele:CA413542193",
    name="NM_005120.3(MED12):c.6352C>T (p.Gln2118Ter)",
    constraints=[
        cat_vrs.Constraint(
            root=cat_vrs.DefiningAlleleConstraint(
                allele=vrs.Allele(
                    id="ga4gh:VA.m-WuNP-2lw3copqMFAEAiiViDp7Re1Rc",
                    digest="m-WuNP-2lw3copqMFAEAiiViDp7Re1Rc",
                    location=vrs.SequenceLocation(
                        id="ga4gh:SL._9hCM5C6a-5s3MtaMeuJsu_uY17HIyf4",
                        digest="_9hCM5C6a-5s3MtaMeuJsu_uY17HIyf4",
                        end=71141314,
                        start=71141313,
                        sequenceReference=vrs.SequenceReference(
                            refgetAccession="SQ.w0WZEvgJF0zf_P4yyTzjjv9oW1z61HHP",
                        ),
                    ),
                    state=vrs.LiteralSequenceExpression(
                        sequence=vrs.sequenceString("T")
                    ),
                )
            )
        )
    ],
)

_put_ca_body = Body(
    description="A canonical allele categorical variant with an ID that references an external knowledgebase record.",
    example=_put_ca_example,
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


@catvar_router.get("/canonical_alleles/{ca_id}", response_model_exclude_none=True)
def get_canonical_allele(request: Request, ca_id: str) -> CanonicalAllele:
    """Fetch a Canonical Allele Categorical Variant by ID"""
    av: AnyVar = request.app.state.anyvar
    ca = av.get_ca_catvar(ca_id)
    if not ca:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND)
    return ca
