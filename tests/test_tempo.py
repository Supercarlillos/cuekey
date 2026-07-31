import pytest

from cuekey.analysis.tempo import (
    BeatGrid,
    detect_tempo,
    fold_bpm,
    pick_metrical_level,
    refine_bpm,
    snap_bpm,
)
from tests.conftest import click_track

import numpy as np


@pytest.mark.parametrize(
    ("raw", "folded"),
    [
        (128.0, 128.0),
        (64.0, 128.0),   # half-tempo error doubled
        (256.0, 128.0),  # double-tempo error halved
        (60.0, 120.0),
        (174.0, 174.0),  # drum & bass stays put
        (200.0, 100.0),
    ],
)
def test_fold_bpm(raw: float, folded: float) -> None:
    assert fold_bpm(raw) == pytest.approx(folded)


def test_detects_click_track_tempo_exactly(sr: int) -> None:
    audio = click_track(bpm=120.0, duration_s=20.0, sr=sr)
    grid = detect_tempo(audio, sr)
    # Beat-grid refinement + integer snapping should land on the exact value,
    # not a quantized tempogram bin like 120.19.
    assert grid.bpm == 120.0
    assert grid.beat_times.size > 10


def test_refine_bpm_uses_mean_beat_interval() -> None:
    beat_times = np.arange(64) * (60.0 / 128.0)  # perfect 128 BPM grid
    assert refine_bpm(999.0, beat_times) == pytest.approx(128.0)
    # Too few beats to trust: fall back to the original estimate.
    assert refine_bpm(125.0, beat_times[:4]) == 125.0


@pytest.mark.parametrize(
    ("raw", "snapped"),
    [
        (127.93, 128.0),   # near-integer -> integer
        (128.14, 128.0),
        (87.46, 87.5),     # near-half -> half
        (126.34, 126.34),  # genuinely fractional -> untouched
    ],
)
def test_snap_bpm(raw: float, snapped: float) -> None:
    assert snap_bpm(raw) == pytest.approx(snapped)


def test_metrical_level_recovers_from_two_thirds_lock(sr: int) -> None:
    import librosa

    audio = click_track(bpm=120.0, duration_s=30.0, sr=sr)
    onset_env = librosa.onset.onset_strength(y=audio, sr=sr, hop_length=512)
    # A tracker locked at 2/3 of the true tempo (80 BPM) must be corrected.
    assert pick_metrical_level(80.0, onset_env, sr) == pytest.approx(120.0)
    # The true tempo must be kept as-is.
    assert pick_metrical_level(120.0, onset_env, sr) == pytest.approx(120.0)


def test_downbeats_are_every_fourth_beat() -> None:
    grid = BeatGrid(bpm=120.0, beat_times=np.arange(16, dtype=float))
    assert list(grid.downbeat_times) == [0.0, 4.0, 8.0, 12.0]
