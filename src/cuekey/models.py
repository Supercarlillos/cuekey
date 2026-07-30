"""Result types shared across analysis, tagging and export modules."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from cuekey.camelot import Key


@dataclass(frozen=True)
class KeyResult:
    key: Key
    confidence: float  # 0..1, margin between best and runner-up correlation


@dataclass(frozen=True)
class CuePoint:
    seconds: float
    label: str = ""


@dataclass
class TrackAnalysis:
    path: Path
    duration: float
    bpm: float
    key: KeyResult
    energy: int  # 1..10
    cues: list[CuePoint] = field(default_factory=list)

    def summary_comment(self, notation: str = "camelot") -> str:
        """Comment-field string, e.g. '8A - Energy 7'."""
        return f"{self.key.key.notation(notation)} - Energy {self.energy}"

    def to_dict(self, notation: str = "camelot") -> dict:
        return {
            "path": str(self.path),
            "duration": round(self.duration, 2),
            "bpm": round(self.bpm, 2),
            "key": self.key.key.standard,
            "key_notation": self.key.key.notation(notation),
            "key_confidence": round(self.key.confidence, 3),
            "energy": self.energy,
            "cues": [round(c.seconds, 3) for c in self.cues],
        }
