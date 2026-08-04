from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

import cuekey.analyzer as analyzer_module
from cuekey.analyzer import analyze_many, default_workers
from cuekey.camelot import MINOR, Key
from cuekey.models import CuePoint, KeyResult, TrackAnalysis


def _fake_analysis(path: Path) -> TrackAnalysis:
    return TrackAnalysis(
        path=path, duration=60.0, bpm=124.0,
        key=KeyResult(key=Key(9, MINOR), confidence=0.8),
        energy=6, cues=[CuePoint(10.0)],
    )


@pytest.fixture()
def cache_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("CUEKEY_CACHE_DIR", str(tmp_path / "cache"))
    return tmp_path / "cache"


@pytest.fixture()
def files(tmp_path: Path) -> list[Path]:
    paths = []
    for name in ("a.wav", "b.wav", "c.wav"):
        path = tmp_path / name
        path.write_bytes(b"\x00" * 64)
        paths.append(path)
    return paths


def test_inline_analyzes_and_fills_cache(
    cache_dir: Path, files: list[Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[Path] = []

    def fake(path: Path, with_cues: bool = True) -> TrackAnalysis:
        calls.append(path)
        return _fake_analysis(path)

    monkeypatch.setattr(analyzer_module, "analyze_file", fake)

    seen: list[Path] = []
    count = analyze_many(files, lambda p, a, e: seen.append(p), max_workers=1)
    assert count == 3
    assert len(calls) == 3
    assert sorted(seen) == sorted(files)

    # Second run: everything comes from the cache, the analyzer is not called.
    calls.clear()
    count = analyze_many(files, lambda p, a, e: seen.append(p), max_workers=1)
    assert count == 3
    assert calls == []


def test_errors_are_reported_not_raised(
    cache_dir: Path, files: list[Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    def flaky(path: Path, with_cues: bool = True) -> TrackAnalysis:
        if path.name == "b.wav":
            raise RuntimeError("decode failed")
        return _fake_analysis(path)

    monkeypatch.setattr(analyzer_module, "analyze_file", flaky)

    errors: list[str] = []
    oks: list[Path] = []

    def on_result(path, analysis, error) -> None:
        if error is not None:
            errors.append(path.name)
        else:
            oks.append(path)

    count = analyze_many(files, on_result, max_workers=1)
    assert count == 2
    assert errors == ["b.wav"]


def test_should_stop_halts_dispatch(
    cache_dir: Path, files: list[Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(analyzer_module, "analyze_file",
                        lambda p, with_cues=True: _fake_analysis(p))
    done: list[Path] = []
    count = analyze_many(
        files, lambda p, a, e: done.append(p),
        max_workers=1, should_stop=lambda: len(done) >= 1,
    )
    assert count == 1
    assert len(done) == 1


def test_default_workers_leaves_headroom() -> None:
    assert default_workers() >= 1


def test_worker_crash_is_isolated_and_batch_continues(
    cache_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A native worker crash (simulated via the CUEKEY_TEST_CRASH hook) must
    not kill the batch: the culprit file gets an error, the rest complete."""
    monkeypatch.setenv("CUEKEY_TEST_CRASH", "1")
    tone = (0.3 * np.sin(2 * np.pi * 220 * np.arange(3 * 22050) / 22050)).astype(np.float32)
    good1, crash, good2 = tmp_path / "g1.wav", tmp_path / "crashme.wav", tmp_path / "g2.wav"
    for path in (good1, good2):
        sf.write(str(path), tone, 22050)
    crash.write_bytes(b"\x00" * 64)

    outcomes: dict[str, str] = {}

    def on_result(path, analysis, error) -> None:
        outcomes[path.name] = "error" if error is not None else "ok"

    count = analyze_many(
        [good1, crash, good2], on_result,
        max_workers=2, use_cache=False, with_cues=False,
    )

    assert count == 2
    assert outcomes["crashme.wav"] == "error"
    assert outcomes["g1.wav"] == "ok"
    assert outcomes["g2.wav"] == "ok"


def test_parallel_pool_end_to_end(cache_dir: Path, tmp_path: Path) -> None:
    """Real process pool with real (tiny) audio files — no monkeypatching
    survives across processes, so this exercises the actual pipeline."""
    tone = (0.3 * np.sin(2 * np.pi * 220 * np.arange(3 * 22050) / 22050)).astype(np.float32)
    paths = []
    for name in ("p1.wav", "p2.wav"):
        path = tmp_path / name
        sf.write(str(path), tone, 22050)
        paths.append(path)

    results: dict[Path, object] = {}
    count = analyze_many(
        paths, lambda p, a, e: results.update({p: a if e is None else e}),
        max_workers=2, use_cache=False, with_cues=False,
    )
    assert count == 2
    for path in paths:
        analysis = results[path]
        assert getattr(analysis, "bpm", None) is not None
        assert 1 <= analysis.energy <= 10
