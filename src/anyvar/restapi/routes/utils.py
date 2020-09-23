# taken from seqrepo-rest-service/src/seqrepo_rest_service/utils.py

from base64 import urlsafe_b64decode, urlsafe_b64encode
from binascii import hexlify, unhexlify
from http.client import responses as http_responses
import logging
import re

import connexion

from bioutils.accessions import infer_namespaces


_logger = logging.getLogger(__name__)


# we return any of these (and accept in Accept header)
valid_content_types = [
    "application/vnd.ga4gh.refget.v1.0.0+json",
    "text/vnd.ga4gh.refget.v1.0.0+plain",
    "application/json",
    "text/plain",
    "*/*",
    ]


def hex_to_base64url(s):
    return urlsafe_b64encode(unhexlify(s)).decode("ascii")

def base64url_to_hex(s):
    return hexlify(urlsafe_b64decode(s)).decode("ascii")

def get_sequence_id(sr, query):
    """determine sequence_ids after guessing form of query

    The query may be:
      * A fully-qualified sequence alias (e.g., VMC:0123 or refseq:NM_01234.5)
      * A digest or digest prefix from VMC, TRUNC512, or MD5
      * A sequence accession (without namespace)
 
    Returns None if not found; seq_id if only one match; raises
    RuntimeError for ambiguous matches. 

    """
    
    seq_ids = get_sequence_ids(sr, query)
    if len(seq_ids) == 0:
        _logger.warning(f"No sequence found for {query}")
        return None
    if len(seq_ids) > 1:
        raise RuntimeError(f"Multiple distinct sequences found for {query}")
    return seq_ids.pop()        # exactly 1 id found


def get_sequence_ids(sr, query):
    """determine sequence_ids after guessing form of query

    The query may be:
      * A fully-qualified sequence alias (e.g., VMC:0123 or refseq:NM_01234.5)
      * A digest or digest prefix from VMC, TRUNC512, or MD5
      * A sequence accession (without namespace)
 
    The first match will be returned.
    """

    nsa_options = _generate_nsa_options(query)
    for ns, a in nsa_options:
        aliases = list(sr.aliases.find_aliases(namespace=ns, alias=a))
        if aliases:
            break
    seq_ids = list(set(a["seq_id"] for a in aliases))
    return seq_ids


def problem(status, message):
    return connexion.problem(status=status, title=http_responses[status], detail=message)



############################################################################
# INTERNAL

def _generate_nsa_options(query):
    """
    >>> _generate_nsa_options("NM_000551.3")
    [('refseq', 'NM_000551.3')]

    >>> _generate_nsa_options("ENST00000530893.6")
    [('ensembl', 'ENST00000530893.6')]

    >>> _generate_nsa_options("gi:123456789")
    [('gi', '123456789')]

    >>> _generate_nsa_options("01234abcde")
    [('MD5', '01234abcde%'), ('VMC', 'GS_ASNKvN4=%')]

    """

    if ":" in query:
        # interpret as fully-qualified identifier
        nsa_options = [tuple(query.split(sep=":", maxsplit=1))]
        return nsa_options

    namespaces = infer_namespaces(query)
    if namespaces:
        nsa_options = [(ns, query) for ns in namespaces]
        return nsa_options
    
    # if hex, try md5 and TRUNC512
    if re.match(r"^(?:[0-9A-Fa-f]{8,})$", query):
        nsa_options = [("MD5", query + "%")]
        # TRUNC512 isn't in seqrepo; synthesize equivalent VMC
        id_b64u = hex_to_base64url(query)
        nsa_options += [("VMC", "GS_" + id_b64u + "%")]
        return nsa_options

    return [(None, query)]
