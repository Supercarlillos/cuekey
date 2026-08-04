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

    if bpm <= 0:
        return bpm
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


def local_maxima(x: np.ndarray) -> np.ndarray:
    """Boolean mask of local maxima (pure numpy)."""
    mask = np.zeros(len(x), dtype=bool)
    if len(x) >= 3:
        mask[1:-1] = (x[1:-1] > x[:-2]) & (x[1:-1] >= x[2:])
    return mask


def estimate_bpm(onset_env: np.ndarray, sr: int) -> float:
    """Base tempo from the onset autocorrelation, scored at 8 beat-period
    multiples over a candidate grid (same idea as pick_metrical_level)."""
    import librosa

    ac = librosa.autocorrelate(onset_env)
    if ac.size == 0 or ac[0] <= 0:
        return 120.0
    ac = ac / ac[0]
    best_bpm, best_score = 120.0, -np.inf
    for candidate in np.arange(MIN_BPM, MAX_BPM, 0.5):
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
        if used:
            score = total / used
            if score > best_score:
                best_bpm, best_score = float(candidate), score
    return best_bpm


def track_beats(onset_env: np.ndarray, sr: int, bpm: float,
                tightness: float = 100.0) -> np.ndarray:
    """Beat positions (frame indices) via Ellis' dynamic-programming tracker.

    Pure numpy implementation — librosa's version relies on numba
    @guvectorize kernels that segfault inside frozen (PyInstaller) apps.
    """
    n = len(onset_env)
    if n == 0 or bpm <= 0:
        return np.array([], dtype=int)
    period = max(1, round(60.0 * sr / (_HOP_LENGTH * bpm)))

    # Smooth the (normalized) envelope with a beat-length gaussian.
    std = onset_env.std(ddof=1)
    normalized = onset_env / std if std > 0 else onset_env
    window = np.exp(-0.5 * ((np.arange(-period, period + 1) * 32.0 / period) ** 2))
    localscore = np.convolve(normalized, window, mode="same")

    # DP: each frame links back to the best predecessor about one period ago.
    backlink = np.full(n, -1, dtype=int)
    cumscore = np.zeros(n)
    offsets = np.arange(-2 * period, -(period // 2) + 1)
    txcost = -tightness * np.log(-offsets / period) ** 2
    for i in range(n):
        window_idx = i + offsets
        valid = window_idx >= 0
        if not valid.any():
            cumscore[i] = localscore[i]
            continue
        scores = txcost[valid] + cumscore[window_idx[valid]]
        best = int(np.argmax(scores))
        cumscore[i] = localscore[i] + scores[best]
        backlink[i] = int(window_idx[valid][best])

    # Last beat: final strong local maximum of the cumulative score.
    maxima = local_maxima(cumscore)
    if not maxima.any():
        return np.array([], dtype=int)
    threshold = 0.5 * np.median(cumscore[maxima][cumscore[maxima] > 0]) \
        if (cumscore[maxima] > 0).any() else 0.0
    strong = np.flatnonzero(maxima & (cumscore >= threshold))
    if strong.size == 0:
        return np.array([], dtype=int)
    beats = [int(strong[-1])]
    while backlink[beats[-1]] >= 0:
        beats.append(int(backlink[beats[-1]]))
    return np.array(beats[::-1], dtype=int)


def detect_tempo(y: np.ndarray, sr: int) -> BeatGrid:
    import librosa

    onset_env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=_HOP_LENGTH)
    bpm = pick_metrical_level(estimate_bpm(onset_env, sr), onset_env, sr)
    beat_frames = track_beats(onset_env, sr, bpm)
    beat_times = librosa.frames_to_time(beat_frames, sr=sr, hop_length=_HOP_LENGTH)
    bpm = snap_bpm(fold_bpm(refine_bpm(bpm, beat_times)))
    return BeatGrid(bpm=round(bpm, 2), beat_times=beat_times)
