"""Tempo (BPM) estimation and beat grid extraction."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

# DJ-oriented plausible range; estimates outside are octave-folded into it.
MIN_BPM = 70.0
MAX_BPM = 180.0


@dataclass
class BeatGrid:
    bpm: float
    beat_times: np.ndarray = field(default_factory=lambda: np.array([]))

    @property
    def downbeat_times(self) -> np.ndarray:
        """Approximate downbeats as every 4th beat from the first one."""
        return self.beat_times[::4]


def fold_bpm(bpm: float, low: float = MIN_BPM, high: float = MAX_BPM) -> float:
    """Fold half/double-tempo estimates into the plausible DJ range."""
    if bpm <= 0:
        return bpm
    while bpm < low:
        bpm *= 2
    while bpm >= high:
        bpm /= 2
    return bpm


def refine_bpm(bpm: float, beat_times: np.ndarray) -> float:
    """Re-derive BPM from the tracked beat grid.

    The tempogram estimate is quantized to coarse bins (a steady 128 BPM
    track can read as 129.2). The mean inter-beat interval is far more
    precise, but quiet intros/outros make the tracker miss beats, so
    intervals far from the median (missed/spurious beats) are discarded
    before averaging.
    """
    if beat_times.size < 16:
        return bpm
    intervals = np.diff(beat_times)
    median = float(np.median(intervals))
    if median <= 0:
        return bpm
    regular = intervals[np.abs(intervals - median) < 0.2 * median]
    if regular.size < 8:
        return bpm
    return 60.0 / float(regular.mean())


def snap_bpm(bpm: float, tolerance: float = 0.2) -> float:
    """Snap near-integer (or near-half) estimates to the clean value.

    DAW-produced music has exact tempos; an estimate of 127.93 is far more
    likely to be a 128.00 track than a genuinely fractional one. Estimates
    farther than the tolerance are kept as-is (vinyl rips, live drummers).
    """
    nearest_int = round(bpm)
    if abs(bpm - nearest_int) <= tolerance:
        return float(nearest_int)
    nearest_half = round(bpm * 2) / 2
    if abs(bpm - nearest_half) <= tolerance / 2:
        return nearest_half
    return bpm


def detect_tempo(y: np.ndarray, sr: int) -> BeatGrid:
    import librosa

    tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr, trim=False)
    bpm = float(np.atleast_1d(tempo)[0])
    beat_times = librosa.frames_to_time(beat_frames, sr=sr)
    bpm = snap_bpm(fold_bpm(refine_bpm(bpm, beat_times)))
    return BeatGrid(bpm=round(bpm, 2), beat_times=beat_times)
