import logging

import biocommons.seqrepo
from biocommons.seqrepo import SeqRepo

import hgvs
from hgvs.dataproviders.uta import connect
from hgvs.parser import Parser


from .utils.digest import vmc_identifer

_logger = logging.getLogger(__name__)


class Translator:
    """Translates various variation formats to VMC"""

    def __init__(self, vmc_bm):
        self.seqrepo = SeqRepo(root_dir="/usr/local/share/seqrepo/latest/")
        self.hdp = connect()
        self.hgvs_parser = Parser()
        self.bm = vmc_bm
    
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

