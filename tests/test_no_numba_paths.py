"""Regression guard: the analysis pipeline must never enter librosa's
numba @guvectorize kernels — they segfault inside frozen (PyInstaller)
apps (NULL gufunc loops). See v0.8.1-0.8.5 changelog saga."""

from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from cuekey.analyzer import analyze_file
from tests.conftest import chord, click_track


@pytest.fixture()
def guarded_librosa(monkeypatch: pytest.MonkeyPatch):
    """Make every frozen-unsafe librosa entry point explode if reached."""
    import librosa

    def boom(name):
        def _fail(*args, **kwargs):
            raise AssertionError(f"forbidden numba path reached: {name}")
        return _fail

    monkeypatch.setattr(librosa.core.pitch, "estimate_tuning", boom("estimate_tuning"))
    monkeypatch.setattr(librosa.core.pitch, "piptrack", boom("piptrack"))
    monkeypatch.setattr(librosa.beat, "beat_track", boom("beat.beat_track"))
    monkeypatch.setattr(librosa.onset, "onset_detect", boom("onset_detect"))
    monkeypatch.setattr(librosa.util, "peak_pick", boom("peak_pick"))
    monkeypatch.setattr(librosa.util, "localmax", boom("util.localmax"))


def test_full_pipeline_avoids_numba_kernels(
    guarded_librosa, tmp_path: Path, sr: int
) -> None:
    audio = (chord(["A3", "C4", "E4"], 6.0, sr=sr) * 0.5
             + click_track(bpm=120.0, duration_s=6.0, sr=sr) * 0.5)
    path = tmp_path / "guarded.wav"
    sf.write(str(path), audio.astype(np.float32), sr)

    analysis = analyze_file(path)  # raises AssertionError on any forbidden path

    assert analysis.bpm > 0
    assert 1 <= analysis.energy <= 10
