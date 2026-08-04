import os
from pathlib import Path

import pytest

import cuekey.cache as cache_module
from cuekey.cache import AnalysisCache
from cuekey.camelot import MINOR, Key
from cuekey.models import CuePoint, KeyResult, TrackAnalysis


def _analysis(path: Path) -> TrackAnalysis:
    return TrackAnalysis(
        path=path,
        duration=180.0,
        bpm=128.0,
        key=KeyResult(key=Key(9, MINOR), confidence=0.9),
        energy=7,
        cues=[CuePoint(1.0, "Cue 1"), CuePoint(30.0, "Cue 2")],
    )


@pytest.fixture()
def cache(tmp_path: Path) -> AnalysisCache:
    return AnalysisCache(db_path=tmp_path / "cache.sqlite")


@pytest.fixture()
def track(tmp_path: Path) -> Path:
    path = tmp_path / "track.wav"
    path.write_bytes(b"\x00" * 128)
    return path


def test_roundtrip(cache: AnalysisCache, track: Path) -> None:
    cache.put(track, _analysis(track))
    hit = cache.get(track)
    assert hit is not None
    assert hit.bpm == 128.0
    assert hit.key.key.standard == "Am"
    assert hit.energy == 7
    assert [c.seconds for c in hit.cues] == [1.0, 30.0]
    assert hit.path == track


def test_miss_for_unknown_file(cache: AnalysisCache, track: Path) -> None:
    assert cache.get(track) is None
    assert cache.get(track.parent / "nonexistent.wav") is None


def test_invalidated_when_file_changes(cache: AnalysisCache, track: Path) -> None:
    cache.put(track, _analysis(track))
    track.write_bytes(b"\x00" * 256)  # different size
    assert cache.get(track) is None


def test_invalidated_when_mtime_changes(cache: AnalysisCache, track: Path) -> None:
    cache.put(track, _analysis(track))
    os.utime(track, ns=(1, 1))
    assert cache.get(track) is None


def test_invalidated_on_algorithm_version_bump(
    cache: AnalysisCache, track: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache.put(track, _analysis(track))
    monkeypatch.setattr(cache_module, "ANALYSIS_VERSION", cache_module.ANALYSIS_VERSION + 1)
    assert cache.get(track) is None


def test_cueless_entry_does_not_satisfy_cue_requests(cache: AnalysisCache, track: Path) -> None:
    cache.put(track, _analysis(track), has_cues=False)
    assert cache.get(track, require_cues=True) is None
    assert cache.get(track, require_cues=False) is not None
