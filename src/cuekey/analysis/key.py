"""Musical key detection.

The whole-track chroma (pitch-class energy) distribution is correlated
against the 24 rotations of the Krumhansl-Kessler major and minor key
profiles (Krumhansl, "Cognitive Foundations of Musical Pitch", 1990).
The best-correlating rotation wins; confidence is the margin over the
runner-up, normalized to 0..1.
"""

from __future__ import annotations

import numpy as np

from cuekey.camelot import MAJOR, MINOR, Key
from cuekey.models import KeyResult

KRUMHANSL_MAJOR = np.array(
    [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88]
)
KRUMHANSL_MINOR = np.array(
    [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17]
)


def _pearson(a: np.ndarray, b: np.ndarray) -> float:
    a = a - a.mean()
    b = b - b.mean()
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)


def detect_key_from_chroma(chroma_mean: np.ndarray) -> KeyResult:
    """Pick the best of 24 keys for a 12-bin averaged chroma vector."""
    scores: list[tuple[float, Key]] = []
    for pitch_class in range(12):
        rotated = np.roll(chroma_mean, -pitch_class)
        scores.append((_pearson(rotated, KRUMHANSL_MAJOR), Key(pitch_class, MAJOR)))
        scores.append((_pearson(rotated, KRUMHANSL_MINOR), Key(pitch_class, MINOR)))

    scores.sort(key=lambda item: item[0], reverse=True)
    best_score, best_key = scores[0]
    runner_up_score = scores[1][0]
    confidence = float(np.clip((best_score - runner_up_score) / 0.2, 0.0, 1.0))
    return KeyResult(key=best_key, confidence=confidence)


def detect_key(y: np.ndarray, sr: int) -> KeyResult:
    """Detect the key of an audio signal."""
    import librosa

    # Kick drums and percussion smear the pitch-class profile; analyze the
    # harmonic component only.
    y_harmonic = librosa.effects.harmonic(y)
    chroma = librosa.feature.chroma_cqt(y=y_harmonic, sr=sr)
    # Median over time is robust against residual noise and transients.
    chroma_mean = np.median(chroma, axis=1)
    return detect_key_from_chroma(chroma_mean)
