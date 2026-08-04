"""Audio loading front-end.

Decoding is delegated to librosa (soundfile first, audioread/ffmpeg as
fallback), downmixed to mono at a fixed analysis sample rate.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

ANALYSIS_SR = 22050

SUPPORTED_EXTENSIONS = {".mp3", ".m4a", ".aac", ".mp4", ".flac", ".wav", ".aiff", ".aif", ".ogg", ".opus"}


def is_supported(path: Path) -> bool:
    # Hidden files include macOS AppleDouble sidecars ("._track.mp3"):
    # metadata blobs that carry an audio extension but contain no audio.
    if path.name.startswith("."):
        return False
    return path.suffix.lower() in SUPPORTED_EXTENSIONS


def load_audio(path: Path, sr: int = ANALYSIS_SR) -> tuple[np.ndarray, int]:
    """Load an audio file as mono float32 at the analysis sample rate."""
    import librosa  # deferred: heavy import

    y, sr = librosa.load(str(path), sr=sr, mono=True)
    if y.size == 0:
        raise ValueError(f"empty or undecodable audio: {path}")
    return y, int(sr)
