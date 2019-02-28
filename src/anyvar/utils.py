import re


format_regexps = {
    "hgvs": [
        # just the accession and variant type
        r"^[^:]+:[cgnopr]",
    ],
    "spdi": [
        # SequenceId:Position:DeletionLength:InsertedSequence
        r"^[^:]+:\d+:(\d+|\w*):\w*"
    ],
    "gnomad": [
        # 1-55516888-G-GA
        r"^\d+-\d+-\w*-\w*$",
    ],
    "beacon": [
        # 13 : 32936732 G > C
        r"\d+\s*:\s*\d+\s*\w+\s*>\s*\w+",
    ],
    "text": [
        r"\w",
        ]
}

format_regexps = {
    t: [re.compile(e) for e in exprs]
    for t, exprs in format_regexps.items()}



def infer_plausible_formats(o):
    """Returns a *set* of plausible formats of the given variation
    definition.  Format inference is permissive: that is, all
    well-formed variation of a particular syntax should be correctly
    recognized, but some invalid variation may be incorrectly
    recognized.  This function will typically return a set with 0 or 1
    item.

    Recognized string formats:
    * "hgvs": NM_000551.3:c.456A>T
    * "spdi": e.g., Seq1:4:AT:CCC
    * "beacon": e.g., 13 : 32936732 G > C
    * "gnomad": 1-55516888-G-GA

    If the input is a list, then the resulting set is the
    *intersection* of this function applied to all members of the
    list.  A list of lists (i.e., a list of list of haplotypes that
    forms a genotype) is supported. Because the intersection of
    inferred types is returned, the data are expected to be
    homogeneously typed. That is, this function is not intended to
    handle cases of a haplotype defined by alleles in different
    formats.

    """

    if o is None:
        return []

    if isinstance(o, list):
        return(set.intersection(infer_plausible_formats(elem) for elem in o))
    
    if isinstance(o, str):
        return set(t
                   for t, exprs in format_regexps.items()
                   if any(e.match(o) for e in exprs))

    raise RuntimeError("Cannot infer format of a " + type(o))



def create_variation(definition, validation_level="relaxed", normalize="right", accept_formats=None):
    """Given a arbitrary object, attempt to parse into a known format. 

    """

    plausible_formats = plausible_formats(definition)
    
    
