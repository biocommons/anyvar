**AnyVar Project Requirements Document**
========================================

**Motivation**
==============

| TODO: alex.wagner@nationwidechildrens.org
| <`reference community need / FAIR Data
  Workshop <https://arxiv.org/abs/2508.13498>`__>.

**Project Goals**
=================

The **Biocommons** **AnyVar project** enables **registration, lookup,
and search of genetic variants** across a distributed genomic resource
network. Its goals are to:

- Provide an **open source**, off-the-shelf solution that lowers the
  technical barriers for genomic data resources to comprehensively
  describe and search genomic variants

- Support a broad range of query modes, including VRS ID lookups, HGVS
  expressions, gene-based searches, and genomic ranges

- Translate community nomenclatures and conventions into a universal
  model for variant representation

- Provide a community-driven, extensible platform for shared conventions
  and policy to realize the above goals

**Use Cases**
=============

As a modular solution to variant registration and search, AnyVar is
envisioned to support a wide variety of Use Cases. We highlight some
envisioned scenarios here:

**Federated Variant Level Matching**
------------------------------------

The Variant Level Matching (VLM) project is for the discovery of
potentially causative variants in rare disease patients. Ad-hoc project
networks have been prototyped, and larger-scale networks are under
development. AnyVar facilitates rapid growth of these networks by:

- Creating a **“batteries-included” VLM-in-a-box node** that connects to
  a federated VLM network

- Enabling institutions to supply their input files (e.g., VCFs) and
  quickly stand up a node that:

  - Registers joint variant call files to aggregate evidence about
    cohort allele frequency

  - Simplifies federated variant queries across the network.

  - Provides answers to questions such as *“Does this variant exist in
    your cohort?”*

- Demonstrating use through a pilot project with the open GREGoR
  consortium data

- Leverages VRS computed identifiers for efficient variant search

**Genomic Classification Resources**
------------------------------------

Genomic classification resources share knowledge and evidence to support
the efficient, robust interpretation of genetic variants. These
resources all require the ability to search and retrieve knowledge
associated with genetic variants using a variety of standardized and
nonstandardized search terms. Some examples of these resources are:

- **ClinVar** - ClinVar aggregates information about genomic variation
  and its relationship to human health

- **CIViC** - Expert-curated web resource that shares expert cancer
  mutation knowledge

- **BRCA Exchange** - serves as a one-stop shop for knowledge on
  germline variants in *BRCA1, BRCA2* and related genes, and their
  impact on cancer susceptibility

AnyVar enables consistency across such resources and reduces their
development and maintenance costs by:

- Enhancing variant search through ongoing community contributions

- Providing a drop-in, open source component for extending genomic data
  resources with robust variant registration and search capabilities

- Enabling resources to link community- or resource-specific variant
  terms to precise and computable variant representations

**Decentralized Variant Mapping Services**
------------------------------------------

Variants with relevance to human health exist in different contexts
beyond the reference human genomes. These may be novel or experimental
sequence references, population-specific genomes, personalized genomes,
and derived sequences such as reference transcripts. Some example
resources that capture and use such mappings include:

- **MaveDB** - provides mappings of evidence on variant impact from
  Multiplexed Assays of Variant Effect (MAVE) experimental sequences to
  human reference sequences

- **ClinGen Allele Registry** - provides mappings of genomic variants
  across GRC human reference assemblies, RefSeq, and Ensembl transcripts
  as Canonical Alleles

- **Online Mendelian Inheritance in Animals (OMIA)** - provides mappings
  of genomic variants associated with heritable traits from animal
  reference sequences to GRC human reference assemblies

AnyVar enables resources to efficiently register and store variant
mappings across reference sequence contexts such as these by:

- Providing a generalized plugin architecture for efficient storage and
  retrieval of variant mappings using modular mapping routines

- Including plugins for community liftover tools that create variant
  mappings across common human reference assemblies (e.g. GRCh37, h38)

- Enabling community reuse of resource-specific sequence mappings

**AnyVar Product Requirements**
===============================

**Primary Data Types**
----------------------

- VRS Objects

  - Alleles

  - Sequence Locations

  - Sequence References

- Key-Value Object Annotations

- Typed Object Mappings

- Typed Object Aliases

**Functionality**
-----------------

- **Variant registration and normalization**

  - Accepts common variant representation formats, including:

    - HGVS

    - SPDI

    - VCF (files and strings)

    - ISCN

    - VRS

  - Ensures conformance with variant representation standards

  - Normalizes and translates between representation formats

  - Stores variant data following community best practices

  - Allows optional definition of aliases and annotations on variant
    registration

  - Supports deletion of variants

- **Bulk import/export of data**

- **VRS object search**

  - Dereferences VRS Object IDs

  - Returns results in a consistent format (VRS)

  - Canonicalizes searches to work across mapped reference sequence
    collections

    - Search on variant, return found variant and mapped variants, each
      with corresponding annotations

  - Supports search by:

    - VRS ids (including sequence, location, variant, or any VRS
      identifiable object)

    - Variant/Location/Sequence Alias, including (but not limited to):

      - HGVS

      - SPDI

      - VCF (**build-chr**-start-stop-ref-alt or
        **axn**-start-stop-ref-alt?)

      - ISCN

      - Accessions

    - Gene

    - Genomic range

  - Does *not* support search by:

    - Annotation values

- **VRS Object Annotation Storage and Lookup**

  - Allows addition and deletion of simple key value associations
    between VRS objects and free text

- **VRS Object Mapping**

  - Providing a generalized plugin architecture for efficient storage
    and retrieval of object mappings using modular mapping routines

  - Including plugins for community liftover tools that create object
    mappings across common human reference assemblies (e.g. GRCh37, h38)

  - Enabling community reuse of resource-specific sequence mappings

- **Portable architecture**

  - Python package

  - REST API

  - Docker deployment

- **Standardized Service Info**

  - Describes version(s) of VRS supported

  - Describes alias types supported

  - Describes assemblies / sequence collections supported by instance

- **Modular components**

  - Mapping plugins (standard and custom)

  - Bring-your-own reference sequence

**Product Roadmap**
===================

**Version 1 (MVP)**
-------------------

**HARD DEADLINE: January 15th, 2026**

*Must support Gregor/VLM-In-A-Box use case.*

AnyVar will support:

- The following **data types**:

  - Alleles

  - SequenceLocation

  - Sequence References

  - Mappings

  - Annotations

- The following **functions**:

  - **Variant registration and normalization**

    - Accepts common variant representation formats, including:

      - HGVS

      - SPDI

      - VCF (files and strings)

      - VRS

    - Ensures conformance with variant representation standards

    - Normalizes and translates between representation formats

    - Stores variant data following community best practices

    - Allows optional definition of annotations

  - **VRS Object search**

    - Dereferences VRS IDs

    - Returns results in a consistent format (VRS)

    - Searches to work across mapped GRCH37 and GRCH38 reference
      assemblies

    - Supports search by:

      - VRS ids (including sequence, location, variant, or any VRS
        identifiable object)

      - Object Aliases, including (but not limited to):

        - HGVS

        - SPDI

        - VCF (**build-chr**-start-stop-ref-alt or
          **axn**-start-stop-ref-alt?)

      - Genomic range

  - **VRS Object Annotation Storage and Lookup**

    - Allows addition of simple key value associations between variants
      and free text

  - **VRS Object Mapping**

    - Enable mapping between GRCh37 and GRCh38

  - **Portable architecture**

    - Python package

    - REST API

    - Docker deployment?

  - **ServiceInfo**:

    - Describe version of VRS supported

    - Describe reference assemblies: GRCh37 and GRCh38

**Version 1.1**
---------------

- The following **data types:**

  - Aliases
  - CNVs
  - Categorical variants

    - Canonical alleles
    - Described CNVs
    - Protein sequence consequence

- The following **functions**:

  - Bulk import/export of dataset (e.g. ClinVar-GKS snapshot release)

  - Allow definition of object aliases

  - Allow definition of object aliases and annotations *on registration*

  - Search by:

    - Genes

    - Chromosome, Accession

    - ISCN

  - Deletion of annotations

  - Deletion of aliases

  - Deletion of variants

**Versions Post 1.1**
---------------------

- The following **data types:**

  - ISCN

- The following **functions**:

  - Allow definition of object aliases and annotations
    *post-registration*

- **VRS Object mapping**

  - Providing a generalized plugin architecture for efficient storage
    and retrieval of object mappings using modular mapping routines

  - Including plugins for community liftover tools that create object
    mappings across common human reference assemblies (e.g. GRCh37, h38)

  - Enabling community reuse of resource-specific sequence mappings

- **Modular components**

  - Mapping plugins (standard and custom)

  - Bring-your-own reference sequence

**Someday/Maybe List**
======================

- bulk load of pre-vrsified representations

- streamline load of vcf with annotated vrs information

- idea: maybe external app could track all the terms used to end up on
  the same variant (meta data?)
