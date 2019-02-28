import logging

import biocommons.seqrepo
from biocommons.seqrepo import SeqRepo

import hgvs
from hgvs.dataproviders.uta import connect
from hgvs.parser import Parser

_logger = logging.getLogger(__name__)


class Translator:
    """Translates various variation formats to VMC"""

    def __init__(self):
        self.seqrepo = SeqRepo(root_dir="/usr/local/share/seqrepo/latest/")
        self.hdp = connect()
        self.hgvs_parser = Parser()
        _logger.warn("initialized translator")

    
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

