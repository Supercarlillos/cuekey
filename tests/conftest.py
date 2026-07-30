"""Shared synthesized-audio fixtures. No copyrighted audio: everything is
generated (sine chords, click tracks, noise sections)."""

from __future__ import annotations

import numpy as np
import pytest

SR = 22050


def sine(freq_hz: float, duration_s: float, sr: int = SR, amp: float = 0.4) -> np.ndarray:
    t = np.arange(int(duration_s * sr)) / sr
    return (amp * np.sin(2 * np.pi * freq_hz * t)).astype(np.float32)


def chord(note_names: list[str], duration_s: float, sr: int = SR, amp: float = 0.2) -> np.ndarray:
    import librosa

    mix = np.zeros(int(duration_s * sr), dtype=np.float32)
    for name in note_names:
        for octave_shift in (0, 12):  # reinforce with the upper octave
            freq = librosa.note_to_hz(name) * (2 ** (octave_shift / 12))
            mix += sine(freq, duration_s, sr, amp)
    peak = np.abs(mix).max()
    return mix / peak * 0.8 if peak > 0 else mix


def click_track(bpm: float, duration_s: float, sr: int = SR) -> np.ndarray:
    import librosa

    interval = 60.0 / bpm
    times = np.arange(0, duration_s, interval)
    return librosa.clicks(times=times, sr=sr, length=int(duration_s * sr)).astype(np.float32)


@pytest.fixture(scope="session")
def sr() -> int:
    return SR
