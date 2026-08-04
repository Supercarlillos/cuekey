"""Energy level (1-10) estimation.

A documented heuristic, not a learned model: combines perceived loudness
(high-percentile RMS), rhythmic onset density, low-frequency (bass) energy
ratio and tempo into a single 1-10 score for planning set intensity.
"""

from __future__ import annotations

import numpy as np

_WEIGHT_LOUDNESS = 0.40
_WEIGHT_ONSETS = 0.25
_WEIGHT_BASS = 0.20
_WEIGHT_TEMPO = 0.15

_BASS_MAX_HZ = 160.0


def _loudness_score(y: np.ndarray) -> float:
    import librosa

    rms = librosa.feature.rms(y=y)[0]
    loud = float(np.percentile(rms, 90))
    db = 20 * np.log10(max(loud, 1e-6))
    # Mastered club tracks sit roughly between -28 dB (mellow) and -8 dB (slamming).
    return float(np.clip((db + 28.0) / 20.0, 0.0, 1.0))


def _onset_score(y: np.ndarray, sr: int) -> float:
    # Count onset-envelope peaks with numpy (librosa's onset_detect goes
    # through numba kernels that are unreliable in frozen apps).
    import librosa

    from cuekey.analysis.tempo import local_maxima

    duration = len(y) / sr
    if duration <= 0:
        return 0.0
    envelope = librosa.onset.onset_strength(y=y, sr=sr)
    if envelope.size == 0:
        return 0.0
    threshold = envelope.mean() + envelope.std()
    peaks = int(np.count_nonzero(local_maxima(envelope) & (envelope >= threshold)))
    rate = peaks / duration  # strong onsets per second
    return float(np.clip(rate / 4.0, 0.0, 1.0))


def _bass_score(y: np.ndarray, sr: int) -> float:
    spectrum = np.abs(np.fft.rfft(y)) ** 2
    freqs = np.fft.rfftfreq(len(y), d=1.0 / sr)
    total = float(spectrum.sum())
    if total == 0:
        return 0.0
    bass = float(spectrum[freqs <= _BASS_MAX_HZ].sum())
    return float(np.clip((bass / total) / 0.5, 0.0, 1.0))


def _tempo_score(bpm: float) -> float:
    return float(np.clip((bpm - 70.0) / 80.0, 0.0, 1.0))


def detect_energy(y: np.ndarray, sr: int, bpm: float) -> int:
    score = (
        _WEIGHT_LOUDNESS * _loudness_score(y)
        + _WEIGHT_ONSETS * _onset_score(y, sr)
        + _WEIGHT_BASS * _bass_score(y, sr)
        + _WEIGHT_TEMPO * _tempo_score(bpm)
    )
    return int(np.clip(round(1 + 9 * score), 1, 10))
