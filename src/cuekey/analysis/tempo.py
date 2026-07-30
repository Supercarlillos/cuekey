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


def detect_tempo(y: np.ndarray, sr: int) -> BeatGrid:
    import librosa

    tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr, trim=False)
    bpm = float(np.atleast_1d(tempo)[0])
    beat_times = librosa.frames_to_time(beat_frames, sr=sr)
    return BeatGrid(bpm=round(fold_bpm(bpm), 2), beat_times=beat_times)
