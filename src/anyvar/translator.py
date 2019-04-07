"""manages a VMC bundle and provides helpful a helpful interface to
it"""

import collections
import datetime
import functools
import logging
import os
import uuid

import biocommons.seqrepo

import hgvs
import hgvs.edit
import hgvs.posedit
import hgvs.parser
import hgvs.location
import hgvs.sequencevariant
from hgvs.dataproviders.uta import connect

import vmc

from .utils.digest import vmc_identifer

_logger = logging.getLogger(__name__)

SEQREPO_ROOT_DIR = os.environ.get("SEQREPO_ROOT_DIR", "/usr/local/share/seqrepo")
SEQREPO_INSTANCE_NAME = os.environ.get("SEQREPO_INSTANCE", "latest")
seqrepo_instance_path = os.path.join(SEQREPO_ROOT_DIR, SEQREPO_INSTANCE_NAME)


# TODO: Implement changeable id style: vmcdigest, serial, uuid

_object_id = 0
def _get_id_serial(o):
    global _object_id
    _object_id += 1
    return str(_object_id)

_id_functions = {
    'computed': vmc.computed_id,
    'serial': _get_id_serial,
    'uuid': lambda _: str(uuid.uuid4()),
    }



class Translator:
    def __init__(self, hdp=None, id_function="computed"):
        # hdp + assemblymapper
        self.seqrepo = biocommons.seqrepo.SeqRepo(seqrepo_instance_path)        
        self.hdp = connect()
        self.hgvs_parser = hgvs.parser.Parser()
        #self.bm = vmc_bm

    def info(self):
        return {
            "seqrepo": {
                "version": biocommons.seqrepo.__version__,
                "instance_directory": self.seqrepo._root_dir,
                },
            "hgvs": {
                "version": hgvs.__version__,
                "dataprovider": str(self.hdp),
                },
            }


    def from_hgvs(self, hgvs):
        """parse and add the hgvs_allele to the bundle"""
        sv = self._hp.parse_hgvs_variant(hgvs)

        sequence_id = self._get_vmc_sequence_identifier(sv.ac)
        self.identifiers[sequence_id].add(sv.ac)

        if isinstance(sv.posedit.pos, hgvs.location.BaseOffsetInterval):
            if sv.posedit.pos.start.is_intronic or sv.posedit.pos.end.is_intronic:
                raise ValueError("Intronic HGVS variants are not supported".format(
                    sv.posedit.edit.type))

        if sv.posedit.edit.type == 'ins':
            interval = models.Interval(start=sv.posedit.pos.start.base,
                                       end=sv.posedit.pos.start.base)
            state = sv.posedit.edit.alt
        elif sv.posedit.edit.type in ('sub', 'del', 'delins', 'identity'):
            interval = models.Interval(start=sv.posedit.pos.start.base - 1,
                                       end=sv.posedit.pos.end.base)
            if sv.posedit.edit.type == 'identity':
                state = get_reference_sequence(sv.ac, sv.posedit.pos.start.base - 1,
                                               sv.posedit.pos.end.base)
            else:
                state = sv.posedit.edit.alt or ''
        else:
            raise ValueError("HGVS variant type {} is unsupported".format(
                sv.posedit.edit.type))

        location = models.Location(sequence_id=sequence_id, interval=interval)
        location.id = self._id_function(location)
        self.locations[location.id] = location

        allele = models.Allele(location_id=location.id, state=state)
        allele.id = self._id_function(allele)
        self.alleles[allele.id] = allele

        return allele


    def _get_vmc_sequence_identifier(self, identifier):
        """return VMC sequence Identifier (string) for a given Identifier from another namespace

        >>> get_vmc_sequence_identifier("RefSeq:NC_000019.10")
        'VMC:GS_IIB53T8CNeJJdUqzn9V_JnRtQadwWCbl'

        >>> get_vmc_sequence_identifier("RefSeq:bogus")
        Traceback (most recent call last):
        ...
        KeyError: 'refseq:bogus'

        # also accepts an Identifier
        >>> from vmc import models
        >>> ir = models.Identifier(namespace="RefSeq", accession="NC_000019.10")
        >>> get_vmc_sequence_identifier(ir)
        'VMC:GS_IIB53T8CNeJJdUqzn9V_JnRtQadwWCbl'

        """

        if isinstance(identifier, vmc.models.Identifier):
            identifier = "{i.namespace}:{i.accession}".format(i=identifier)
        return self._sr.translate_identifier(identifier, target_namespaces=["VMC"])[0]



    def create_allele(self, defn):
        result = {
            "id": None,
            "data": None,
            "type": None,
            "messages": [],
            }

        try:
            a = self.bm.add_hgvs_allele(defn)
            result["messages"].append("parsed as HGVS allele")
            result["data"] = a.as_dict()
            result["id"] = vmc_identifer("GA", result["data"])
            result["type"] = "allele"
        except Exception as e:
            result["messages"].append("hgvs parser: " + str(e))

        return result

    
    def create_text_variation(self, defn):
        return {
            "id": vmc_identifer("GT", defn),
            "messages": [],
            "data": defn,
            "type": "text",
            }
