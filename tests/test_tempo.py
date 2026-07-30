import pytest

from cuekey.analysis.tempo import BeatGrid, detect_tempo, fold_bpm
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


def test_detects_click_track_tempo(sr: int) -> None:
    audio = click_track(bpm=120.0, duration_s=20.0, sr=sr)
    grid = detect_tempo(audio, sr)
    assert grid.bpm == pytest.approx(120.0, abs=3.0)
    assert grid.beat_times.size > 10


def test_downbeats_are_every_fourth_beat() -> None:
    grid = BeatGrid(bpm=120.0, beat_times=np.arange(16, dtype=float))
    assert list(grid.downbeat_times) == [0.0, 4.0, 8.0, 12.0]
