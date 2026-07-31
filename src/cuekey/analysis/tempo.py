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


# Common metrical confusions of beat trackers: 3:2 (syncopation), octave, 4:3.
_METRICAL_FACTORS = (1.5, 2 / 3, 2.0, 0.5, 4 / 3, 0.75)
_HOP_LENGTH = 512
_SWITCH_MARGIN = 1.05  # only re-level if clearly better, to avoid flip-flopping


def pick_metrical_level(bpm: float, onset_env: np.ndarray, sr: int) -> float:
    """Resolve metrical-level errors (e.g. locking onto 2/3 of the true tempo).

    Each candidate tempo is scored by the mean autocorrelation of the onset
    envelope at the first 8 multiples of its beat period: the true tempo
    aligns at every multiple, while a 3:2 mislock misses the odd ones.
    """
    import librosa

    ac = librosa.autocorrelate(onset_env)
    if ac.size == 0 or ac[0] <= 0:
        return bpm
    ac = ac / ac[0]

    def score(candidate: float) -> float:
        lag = 60.0 * sr / (_HOP_LENGTH * candidate)
        total, used = 0.0, 0
        for k in range(1, 9):
            index = k * lag
            i0 = int(index)
            if i0 + 1 >= ac.size:
                break
            frac = index - i0
            total += (1 - frac) * ac[i0] + frac * ac[i0 + 1]
            used += 1
        return total / used if used else 0.0

    base_score = score(bpm)
    best_bpm, best_score = bpm, base_score
    for factor in _METRICAL_FACTORS:
        candidate = fold_bpm(bpm * factor)
        candidate_score = score(candidate)
        if candidate_score > best_score:
            best_bpm, best_score = candidate, candidate_score
    if best_bpm != bpm and best_score > _SWITCH_MARGIN * base_score:
        return best_bpm
    return bpm


def detect_tempo(y: np.ndarray, sr: int) -> BeatGrid:
    import librosa

    onset_env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=_HOP_LENGTH)
    tempo, beat_frames = librosa.beat.beat_track(
        onset_envelope=onset_env, sr=sr, hop_length=_HOP_LENGTH, trim=False
    )
    beat_times = librosa.frames_to_time(beat_frames, sr=sr, hop_length=_HOP_LENGTH)
    bpm = fold_bpm(refine_bpm(float(np.atleast_1d(tempo)[0]), beat_times))

    releveled = pick_metrical_level(bpm, onset_env, sr)
    if abs(releveled - bpm) > 0.5:
        # Re-track beats at the corrected tempo so the grid (and cue
        # snapping) matches, then re-refine on the new grid.
        _, beat_frames = librosa.beat.beat_track(
            onset_envelope=onset_env, sr=sr, hop_length=_HOP_LENGTH,
            bpm=releveled, trim=False,
        )
        beat_times = librosa.frames_to_time(beat_frames, sr=sr, hop_length=_HOP_LENGTH)
        bpm = fold_bpm(refine_bpm(releveled, beat_times))
    bpm = snap_bpm(bpm)
    return BeatGrid(bpm=round(bpm, 2), beat_times=beat_times)
