# ruff: noqa: SLF001
from __future__ import annotations

from dataclasses import dataclass, field

import pytest
from biocommons.seqrepo import SeqRepo

from anyvar.translate.vrs_python import WindowedSeqRepoDataProxy

SEQ = "AGCT" * 50_000


@dataclass
class FakeSeqRepo(SeqRepo):
    """Minimal fake SeqRepo with alias support + call counting."""

    # map identifier -> canonical id (aliases all map to one canonical id)
    canonical_of: dict[str, str] = field(default_factory=dict)
    # map canonical id -> full sequence
    sequences: dict[str, str] = field(default_factory=dict)
    calls: list[tuple[str, int | None, int | None]] = field(default_factory=list)

    def fetch_uri(
        self, uri: str, start: int | None = None, end: int | None = None
    ) -> str:
        self.calls.append((uri, start, end))
        canonical = self.canonical_of.get(uri, uri)
        seq = self.sequences[canonical]
        # mimic python slicing behavior for None bounds
        return seq[start:end]


@pytest.fixture
def fake_sr() -> FakeSeqRepo:
    # Two aliases pointing to the same underlying sequence:
    # "ga4gh:SQ.1" and "refget:SQ.1" -> "SQ.1"
    return FakeSeqRepo(
        canonical_of={
            "ga4gh:SQ.1": "SQ.1",
            "refget:SQ.1": "SQ.1",
            "SQ.1": "SQ.1",
        },
        sequences={"SQ.1": SEQ},
    )


@pytest.fixture
def dataproxy(fake_sr: FakeSeqRepo, monkeypatch):
    """
    Build the proxy and:
      - force coerce_namespace() to identity so tests don't depend on namespace logic
      - reduce chunk size so tests are small/fast
    """
    import anyvar.translate.vrs_python as mod  # noqa: PLC0415

    monkeypatch.setattr(mod, "coerce_namespace", lambda x: x)

    p = mod.WindowedSeqRepoDataProxy(fake_sr)
    p._chunk_size = 20  # make windows tiny so we can test window edges easily
    return p


@pytest.mark.ci_ok
def test_first_small_request_populates_cache(
    dataproxy: WindowedSeqRepoDataProxy, fake_sr
):
    # Miss -> should fetch a full window [start, start+chunk)
    got = dataproxy.get_sequence("ga4gh:SQ.1", 3, 8)
    assert got == SEQ[3:8]

    assert fake_sr.calls == [("ga4gh:SQ.1", 3, 3 + dataproxy._chunk_size)]
    assert dataproxy._seq_start == 3
    assert dataproxy._seq_end == 3 + dataproxy._chunk_size
    assert dataproxy._seq == SEQ[3 : 3 + dataproxy._chunk_size]
    assert dataproxy._cached_ids == {"ga4gh:SQ.1"}


@pytest.mark.ci_ok
def test_second_request_within_window_is_cache_hit(dataproxy, fake_sr):
    dataproxy.get_sequence("ga4gh:SQ.1", 3, 8)
    fake_sr.calls.clear()

    got = dataproxy.get_sequence("ga4gh:SQ.1", 5, 10)
    assert got == SEQ[5:10]
    assert fake_sr.calls == []  # cache hit, no fetch


@pytest.mark.ci_ok
def test_request_outside_window_is_cache_miss_and_rewindows(dataproxy, fake_sr):
    dataproxy.get_sequence("ga4gh:SQ.1", 0, 5)
    fake_sr.calls.clear()

    # Outside previous window (chunk=20, window is [0,20); choose start=25)
    got = dataproxy.get_sequence("ga4gh:SQ.1", 25, 30)
    assert got == SEQ[25:30]

    assert fake_sr.calls == [("ga4gh:SQ.1", 25, 25 + dataproxy._chunk_size)]
    assert dataproxy._seq_start == 25
    assert dataproxy._seq_end == 45
    assert dataproxy._cached_ids == {"ga4gh:SQ.1"}


@pytest.mark.ci_ok
def test_alias_is_learned_when_fetch_returns_same_sequence(dataproxy, fake_sr):
    # Prime cache using first alias
    dataproxy.get_sequence("ga4gh:SQ.1", 10, 15)

    # Now query using the *other* alias within a different window so it triggers a fetch
    # That fetch should return the *same window sequence* as the cache iff start matches.
    # So use the same start to force equality and exercise the alias-add path.
    fake_sr.calls.clear()
    dataproxy.get_sequence("refget:SQ.1", 10, 12)

    # It had to fetch once for the new ID (since it's not yet in cached_ids)
    assert fake_sr.calls == [("refget:SQ.1", 10, 10 + dataproxy._chunk_size)]
    # Because the fetched window equals the cached window, dataproxy should add the alias:
    assert dataproxy._cached_ids == {"ga4gh:SQ.1", "refget:SQ.1"}

    # Now the alias should be a cache hit (no additional fetch)
    fake_sr.calls.clear()
    got = dataproxy.get_sequence("refget:SQ.1", 11, 14)
    assert got == SEQ[11:14]
    assert fake_sr.calls == []


@pytest.mark.ci_ok
def test_large_request_delegates_directly_and_does_not_change_cache(dataproxy, fake_sr):
    # Prime cache with something small
    dataproxy.get_sequence("ga4gh:SQ.1", 0, 5)
    cached_state = (
        dataproxy._seq_start,
        dataproxy._seq_end,
        dataproxy._seq,
        set(dataproxy._cached_ids),
    )
    fake_sr.calls.clear()

    # end-start >= chunk_size => delegate directly
    got = dataproxy.get_sequence("ga4gh:SQ.1", 0, dataproxy._chunk_size)
    assert got == SEQ[0 : dataproxy._chunk_size]

    # Called with the original bounds (not a window fetch)
    assert fake_sr.calls == [("ga4gh:SQ.1", 0, dataproxy._chunk_size)]
    assert (
        dataproxy._seq_start,
        dataproxy._seq_end,
        dataproxy._seq,
        set(dataproxy._cached_ids),
    ) == cached_state


@pytest.mark.parametrize(
    ("start", "end"),
    [
        (None, 10),
        (0, None),
        (None, None),
    ],
)
@pytest.mark.ci_ok
def test_unbounded_requests_delegate_directly(dataproxy, fake_sr, start, end):
    fake_sr.calls.clear()
    got = dataproxy.get_sequence("ga4gh:SQ.1", start, end)
    assert got == SEQ[start:end]
    assert fake_sr.calls == [("ga4gh:SQ.1", start, end)]


@pytest.mark.ci_ok
def test_end_at_window_boundary_is_hit(dataproxy, fake_sr):
    # window [10, 30)
    dataproxy.get_sequence("ga4gh:SQ.1", 10, 12)
    fake_sr.calls.clear()

    # end == seq_end should still be a hit (end <= _seq_end)
    got = dataproxy.get_sequence("ga4gh:SQ.1", 25, 30)
    assert got == SEQ[25:30]
    assert fake_sr.calls == []


@pytest.mark.ci_ok
def test_start_before_window_is_miss(dataproxy, fake_sr):
    dataproxy.get_sequence("ga4gh:SQ.1", 10, 12)
    fake_sr.calls.clear()

    got = dataproxy.get_sequence("ga4gh:SQ.1", 9, 11)
    assert got == SEQ[9:11]
    assert fake_sr.calls == [("ga4gh:SQ.1", 9, 9 + dataproxy._chunk_size)]
