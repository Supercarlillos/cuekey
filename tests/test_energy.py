import numpy as np

from cuekey.analysis.energy import detect_energy
from tests.conftest import click_track, sine


def test_loud_dense_track_scores_higher_than_quiet_pad(sr: int) -> None:
    quiet = sine(440.0, duration_s=10.0, sr=sr, amp=0.02)
    loud = (
        click_track(bpm=140.0, duration_s=10.0, sr=sr) * 0.9
        + sine(60.0, duration_s=10.0, sr=sr, amp=0.5)
    )
    energy_quiet = detect_energy(quiet, sr, bpm=80.0)
    energy_loud = detect_energy(loud, sr, bpm=140.0)
    assert energy_loud > energy_quiet


def test_energy_stays_in_range(sr: int) -> None:
    silence = np.zeros(sr * 2, dtype=np.float32)
    assert 1 <= detect_energy(silence, sr, bpm=0.0) <= 10

    slamming = click_track(bpm=175.0, duration_s=5.0, sr=sr) + sine(50.0, 5.0, sr, amp=0.9)
    assert 1 <= detect_energy(slamming, sr, bpm=175.0) <= 10
