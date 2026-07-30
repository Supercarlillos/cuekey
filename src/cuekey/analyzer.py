"""Full-track analysis pipeline: key + tempo + energy + cues."""

from __future__ import annotations

from pathlib import Path

from cuekey.analysis.cues import detect_cues
from cuekey.analysis.energy import detect_energy
from cuekey.analysis.key import detect_key
from cuekey.analysis.tempo import detect_tempo
from cuekey.audio import load_audio
from cuekey.models import TrackAnalysis


def analyze_file(path: Path, with_cues: bool = True) -> TrackAnalysis:
    y, sr = load_audio(path)
    duration = len(y) / sr

    grid = detect_tempo(y, sr)
    key = detect_key(y, sr)
    energy = detect_energy(y, sr, grid.bpm)
    cues = detect_cues(y, sr, grid) if with_cues else []

    return TrackAnalysis(
        path=path,
        duration=duration,
        bpm=grid.bpm,
        key=key,
        energy=energy,
        cues=cues,
    )
