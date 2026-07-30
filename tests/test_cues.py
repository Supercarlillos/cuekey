import numpy as np

from cuekey.analysis.cues import MAX_CUES, MIN_CUE_SPACING_SECONDS, detect_cues, snap_to_grid
from cuekey.analysis.tempo import detect_tempo
from tests.conftest import click_track, sine


def test_snap_to_grid() -> None:
    grid = np.array([0.0, 2.0, 4.0, 6.0])
    assert snap_to_grid(2.4, grid) == 2.0
    assert snap_to_grid(4.9, grid) == 4.0
    assert snap_to_grid(5.1, grid) == 6.0
    assert snap_to_grid(3.0, np.array([])) == 3.0


def _two_section_track(sr: int) -> np.ndarray:
    quiet_intro = sine(220.0, duration_s=15.0, sr=sr, amp=0.05)
    rng = np.random.default_rng(seed=7)
    noise = rng.standard_normal(15 * sr).astype(np.float32) * 0.3
    loud_drop = click_track(bpm=128.0, duration_s=15.0, sr=sr) + noise
    return np.concatenate([quiet_intro, loud_drop])


def test_finds_structural_boundary(sr: int) -> None:
    audio = _two_section_track(sr)
    grid = detect_tempo(audio, sr)
    cues = detect_cues(audio, sr, grid)

    assert 1 <= len(cues) <= MAX_CUES
    # A cue must land near the quiet->loud transition at t=15s.
    assert any(abs(c.seconds - 15.0) < 5.0 for c in cues)


def test_cues_are_sorted_and_spaced(sr: int) -> None:
    audio = _two_section_track(sr)
    grid = detect_tempo(audio, sr)
    times = [c.seconds for c in detect_cues(audio, sr, grid)]

    assert times == sorted(times)
    assert all(b - a >= MIN_CUE_SPACING_SECONDS for a, b in zip(times, times[1:]))
