"""Automatic cue point suggestion.

Tracks are segmented by clustering timbre+harmony features over time
(agglomerative segmentation on MFCC + chroma). Segment boundaries mark
structural changes (intro, breakdown, drop, outro); each boundary is
snapped to the nearest downbeat so cues land on the beat grid.
"""

from __future__ import annotations

import numpy as np

from cuekey.analysis.tempo import BeatGrid
from cuekey.models import CuePoint

MAX_CUES = 8
MIN_CUE_SPACING_SECONDS = 8.0


def snap_to_grid(time: float, grid_times: np.ndarray) -> float:
    """Snap a time to the nearest grid point (returns time if grid empty)."""
    if grid_times.size == 0:
        return time
    index = int(np.argmin(np.abs(grid_times - time)))
    return float(grid_times[index])


def _deduplicate(times: list[float], min_spacing: float) -> list[float]:
    kept: list[float] = []
    for time in sorted(times):
        if not kept or time - kept[-1] >= min_spacing:
            kept.append(time)
    return kept


def _segment_boundaries(y: np.ndarray, sr: int, n_segments: int) -> list[float]:
    import librosa

    hop = 512
    mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13, hop_length=hop)
    # tuning=0.0 skips estimate_tuning (numba kernels, unreliable frozen).
    chroma = librosa.feature.chroma_stft(y=y, sr=sr, hop_length=hop, tuning=0.0)
    features = np.vstack([mfcc, chroma])
    # Normalize each feature row so no single dimension dominates clustering.
    features = librosa.util.normalize(features, axis=1)

    n_frames = features.shape[1]
    n_segments = min(n_segments, max(2, n_frames // 4))
    boundary_frames = librosa.segment.agglomerative(features, n_segments)
    boundary_times = librosa.frames_to_time(boundary_frames, sr=sr, hop_length=hop)
    # First boundary is always frame 0; keep it (intro cue) plus the rest.
    return [float(t) for t in boundary_times]


def detect_cues(
    y: np.ndarray,
    sr: int,
    grid: BeatGrid,
    max_cues: int = MAX_CUES,
) -> list[CuePoint]:
    duration = len(y) / sr
    boundaries = _segment_boundaries(y, sr, n_segments=max_cues + 2)

    downbeats = grid.downbeat_times
    snapped = [snap_to_grid(t, downbeats) for t in boundaries]
    # Ignore boundaries in the final seconds: not useful as cues.
    snapped = [t for t in snapped if t < duration - 5.0]
    times = _deduplicate(snapped, MIN_CUE_SPACING_SECONDS)[:max_cues]

    return [CuePoint(seconds=t, label=f"Cue {i + 1}") for i, t in enumerate(times)]
