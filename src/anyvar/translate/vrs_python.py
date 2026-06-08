"""Normalize incoming variation descriptions with the VRS-Python library."""

import logging
from enum import StrEnum
from os import environ
from typing import Any
from warnings import warn

from biocommons.seqrepo import SeqRepo
from bioutils.accessions import coerce_namespace
from ga4gh.vrs import models
from ga4gh.vrs.dataproxy import (
    DataProxyValidationError,
    SeqRepoDataProxy,
    _DataProxy,
    create_dataproxy,
)
from ga4gh.vrs.extras.translator import AlleleTranslator, CnvTranslator
from hgvs.exceptions import HGVSParseError

from anyvar.core.objects import SupportedVrsVariation
from anyvar.translate.base import TranslationError, Translator

_logger = logging.getLogger(__name__)


class TranslatorConfigOption(StrEnum):
    """Translator configuration options supported by VRS-Python.

    These values are used to filter user-provided keyword arguments before
    passing them to VRS-Python translation methods.
    """

    FMT = "fmt"
    ASSEMBLY_NAME = "assembly_name"
    REQUIRE_VALIDATION = "require_validation"
    RLE_SEQ_LIMIT = "rle_seq_limit"
    REF_SEQ_LIMIT = "ref_seq_limit"
    NAMESPACE = "namespace"


class WindowedSeqRepoDataProxy(SeqRepoDataProxy):
    """SeqRepo proxy with fixed-size window caching.

    Optimizes repeated small range queries by caching a single fixed-size sequence
    window and serving subsequent sub-range requests from memory when possible.

    .. warning::

       This API is still experimental, and is subject to change.

    If a request falls outside the cached window or exceeds the configured chunk size,
    it is delegated directly to SeqRepo.
    """

    def __init__(self, sr: SeqRepo) -> None:
        """Initialize DataProxy instance.

        :param sr: SeqRepo instance
        """
        warn(
            "WindowedSeqRepoDataProxy is experimental, and its module path and API may change in future releases",
            category=FutureWarning,
            stacklevel=2,
        )
        super().__init__(sr)
        self._chunk_size = 100000
        self._cached_ids = set()
        # initialize window start/end with illegal values so that first request is always a miss
        self._seq_start, self._seq_end = -1, -1
        self._seq = ""
        _logger.info("Initialized windowed-caching seqrepo dataproxy")

    def _get_sequence(
        self, identifier: str, start: int | None = None, end: int | None = None
    ) -> str:
        """Return a sequence slice, using a fixed-size window cache when possible.

        For small range queries (< self._chunk_size), this method fetches and caches
        a contiguous window of sequence starting at ``start``. Subsequent requests
        that fall within the cached window are served directly from memory.

        The cache stores:
          - a single sequence window
          - its genomic start/end bounds
          - identifiers known to resolve to the same underlying sequence

        This optimization improves performance for workloads exhibiting
        spatial locality (many nearby small slice requests).

        :param identifier: full sequence ID
        :param start: optional starting position
        :param end: optional ending position
        :return: literal sequence
        """
        namespaced_id = coerce_namespace(identifier)

        # Delegate large or unbounded requests directly to SeqRepo
        if (start is None or end is None) or (end - start >= self._chunk_size):
            return self.sr.fetch_uri(namespaced_id, start, end)

        # cache hit
        if (
            namespaced_id in self._cached_ids
            and start >= self._seq_start
            and end <= self._seq_end
        ):
            return self._seq[start - self._seq_start : end - self._seq_start]

        sequence = self.sr.fetch_uri(namespaced_id, start, start + self._chunk_size)
        if self._seq == "" or self._seq != sequence:
            self._cached_ids = {namespaced_id}
            self._seq_start = start
            self._seq_end = start + self._chunk_size
            self._seq = sequence
        elif sequence == self._seq:
            # update the known aliases for this sequence and try again
            self._cached_ids.add(namespaced_id)
        return self._get_sequence(namespaced_id, start, end)


class VrsPythonTranslator(Translator):
    """Translator layer using VRS-Python Translator class."""

    def __init__(
        self, seqrepo_proxy: _DataProxy | None = None, disable_healthcheck: bool = False
    ) -> None:
        """Initialize VRS-Python translator.

        If an existing SeqRepo data proxy is not provided, use the VRS-Python
        ``create_dataproxy`` function to construct one. The following URI patterns
        can be used to specify a local file instance or an address to REST service:

        * seqrepo+file:///path/to/seqrepo/root
        * seqrepo+:../relative/path/to/seqrepo/root
        * seqrepo+http://localhost:5000/seqrepo
        * seqrepo+https://somewhere:5000/seqrepo

        We'll pass the value defined under the environment variable
        ``SEQREPO_DATAPROXY_URI``, and default to local service
        (``"seqrepo+http://localhost:5000/seqrepo"``) if it's undefined.

        :param seqrepo_proxy: existing SR proxy instance if available.
        :param disable_healthcheck: Whether or not to disable the health check for REST
            dataproxy
        """
        if not seqrepo_proxy:
            seqrepo_uri = environ.get(
                "SEQREPO_DATAPROXY_URI", "seqrepo+http://localhost:5000/seqrepo"
            )
            self.dp = create_dataproxy(
                seqrepo_uri, disable_healthcheck=disable_healthcheck
            )
        else:
            self.dp = seqrepo_proxy
        self.allele_tlr = AlleleTranslator(data_proxy=self.dp)
        self.cnv_tlr = CnvTranslator(data_proxy=self.dp)

    @staticmethod
    def _filter_translator_kwargs(
        kwargs: dict[str, Any],
        allowed_options: tuple[TranslatorConfigOption, ...],
    ) -> dict[str, Any]:
        """Filter translator configuration options from user-provided kwargs.

        :param kwargs: User-provided keyword arguments.
        :param allowed_options: Translator configuration options supported by the
            translation method being called.
        :return: Translator keyword arguments supported by the requested
            translation method.
        """
        return {
            option.value: kwargs[option.value]
            for option in allowed_options
            if option.value in kwargs
        }

    def translate_variation(self, var: str, **kwargs) -> SupportedVrsVariation:
        """Translate provided variation text into a VRS Variation object.

        :param var: user-provided string describing or referencing a variation.
        :param kwargs: Additional translation options.

            * assembly_name (str): Assembly name for ``var``.
                Only used when ``var`` uses gnomad format.
                Defaults to "GRCh38".
                VRS-Python sets a default, but we should set a default just in case VRS-Python ever changes the default.
            * require_validation (bool): Whether validation checks must pass in order to
                return a VRS Allele.
            * rle_seq_limit (int | None): If RLE is set as the new state after
                normalization, this sets the limit for the length of the `sequence`.
                To exclude `sequence` from the response, set to 0.
                For no limit, set to `None`.
        :returns: VRS variation object
        :raises TranslationError: if translation is unsuccessful, either because
            the submitted variation is malformed, uses an unsupported identifier format,
            fails validation checks, or is not supported by VRS-Python.
        """
        try:
            variation = self.translate_allele(var, **kwargs)
        except TranslationError as e:
            raise TranslationError(str(e)) from e
        return variation

    def translate_allele(self, var: str, **kwargs) -> models.Allele:
        """Translate provided variation text into a VRS Allele object.

        :param var: user-provided string describing or referencing a variation.
        :param kwargs: Additional translation options.

            * fmt (str | TranslateFromIdentifierFormat | None): The format of ``var``. If None, will guess the appropriate format.
            * assembly_name (str): Assembly name for ``var``.
                Only used when ``var`` uses gnomad format.
                Defaults to "GRCh38".
                VRS-Python sets a default, but we should set a default just in case VRS-Python ever changes the default.
            * require_validation (bool): Whether validation checks must pass in order to
                return a VRS Allele.
            * rle_seq_limit (int | None): If RLE is set as the new state after
                normalization, this sets the limit for the length of the `sequence`.
                To exclude `sequence` from the response, set to 0.
                For no limit, set to `None`.
        :returns: VRS Allele object if able to translate
        :raises TranslationError: if translation is unsuccessful, either because
            the submitted variation is malformed, uses an unsupported identifier format,
            fails validation checks, or is not supported by VRS-Python.
        """
        translator_kwargs = self._filter_translator_kwargs(
            kwargs,
            (
                TranslatorConfigOption.FMT,
                TranslatorConfigOption.ASSEMBLY_NAME,
                TranslatorConfigOption.REQUIRE_VALIDATION,
                TranslatorConfigOption.RLE_SEQ_LIMIT,
            ),
        )
        try:
            return self.allele_tlr.translate_from(var, **translator_kwargs)  # type: ignore (this will always return a models.Allele instance, or raise a ValueError)
        except ValueError as e:
            raise TranslationError(str(e)) from e
        except DataProxyValidationError as e:
            raise TranslationError(str(e)) from e
        except HGVSParseError as e:
            msg = f'Unable to parse HGVS expression "{var}"'
            raise TranslationError(msg) from e
        except NotImplementedError as e:
            msg = f'Variation class for "{var}" is currently unsupported.'
            raise TranslationError(msg) from e

    def translate_allele_to_format(
        self, allele: models.Allele, fmt: str, **kwargs
    ) -> list[str]:
        """Translate a VRS Allele to one or more identifiers in the requested format.

        :param allele: VRS Allele to translate.
        :param fmt: Target identifier format (e.g. hgvs, spdi)
        :param kwargs: Additional translation options.

            * namespace (str | None): Namespace to return identifiers for. If None,
                returns all alias translations.
            * ref_seq_limit (int | None):
                Only used for SPDI
                If ``allele.state`` is a ReferenceLengthExpression, and `ref_seq_limit`
                is specified, the reference sequence is included in the SPDI expression
                if it is below the limit.
                Otherwise only the length of the reference sequence is included.
                If the limit is None, the reference sequence is always included.
                In all cases, the alt sequence is included.
                Default is 0 (never include reference sequence).
        :return: List of translated identifiers in the requested format.
        :raises TranslationError: If translation is unsuccessful because required
            reference sequence information cannot be resolved, the allele is invalid,
            or the requested format is unsupported by VRS-Python.
        """
        translator_kwargs = self._filter_translator_kwargs(
            kwargs,
            (TranslatorConfigOption.NAMESPACE, TranslatorConfigOption.REF_SEQ_LIMIT),
        )
        try:
            return self.allele_tlr.translate_to(allele, fmt, **translator_kwargs)  # type: ignore
        except KeyError as e:
            msg = f"Identifier not found: {e}"
            raise TranslationError(msg) from e
        except (ValueError, AssertionError, NotImplementedError) as e:
            msg = f'Unable to translate allele to "{fmt}": {e}'
            raise TranslationError(msg) from e

    def get_sequence_id(self, accession_id: str) -> str:
        """Get GA4GH sequence identifier for provided accession ID

        :param accession_id: ID to convert
        :return: equivalent GA4GH sequence ID
        :raise: KeyError if no equivalent ID is available
        """
        result = self.allele_tlr.data_proxy.translate_sequence_identifier(
            accession_id, "ga4gh"
        )
        return result[0]
