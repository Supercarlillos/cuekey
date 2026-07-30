"""Musical key representation and harmonic-mixing wheel notations.

A key is a pitch class (0 = C ... 11 = B) plus a mode (major/minor).
Supported notations:
- standard:  "Am", "F#m", "C", "Eb"
- camelot:   "8A" (minor) / "8B" (major), the de facto wheel numbering
- openkey:   "1m" (minor) / "1d" (major), as used by other DJ software
"""

from __future__ import annotations

from dataclasses import dataclass

PITCH_NAMES_SHARP = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
PITCH_NAMES_FLAT = ["C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B"]

MAJOR = "major"
MINOR = "minor"

_NAME_TO_PITCH = {name: pc for pc, name in enumerate(PITCH_NAMES_SHARP)}
_NAME_TO_PITCH.update({name: pc for pc, name in enumerate(PITCH_NAMES_FLAT)})


@dataclass(frozen=True)
class Key:
    pitch_class: int  # 0 = C ... 11 = B
    mode: str  # "major" | "minor"

    def __post_init__(self) -> None:
        if not 0 <= self.pitch_class <= 11:
            raise ValueError(f"pitch_class out of range: {self.pitch_class}")
        if self.mode not in (MAJOR, MINOR):
            raise ValueError(f"unknown mode: {self.mode}")

    @property
    def standard(self) -> str:
        suffix = "m" if self.mode == MINOR else ""
        return PITCH_NAMES_SHARP[self.pitch_class] + suffix

    @property
    def wheel_number(self) -> int:
        """Position 1-12 on the harmonic wheel (shared by camelot/openkey)."""
        if self.mode == MAJOR:
            tonic = self.pitch_class
        else:
            tonic = (self.pitch_class + 3) % 12  # relative major
        return (tonic * 7 + 7) % 12 + 1

    @property
    def camelot(self) -> str:
        letter = "B" if self.mode == MAJOR else "A"
        return f"{self.wheel_number}{letter}"

    @property
    def openkey(self) -> str:
        number = (self.wheel_number + 4) % 12 + 1
        letter = "d" if self.mode == MAJOR else "m"
        return f"{number}{letter}"

    def notation(self, style: str) -> str:
        match style:
            case "standard":
                return self.standard
            case "camelot":
                return self.camelot
            case "openkey":
                return self.openkey
            case _:
                raise ValueError(f"unknown notation style: {style}")

    def __str__(self) -> str:
        return self.standard


def parse_key(text: str) -> Key:
    """Parse a key from standard notation like 'Am', 'F#m', 'Bb' or 'C'."""
    text = text.strip()
    if not text:
        raise ValueError("empty key string")
    mode = MINOR if text.endswith(("m", "min")) else MAJOR
    name = text.rstrip("min") if text.endswith("min") else text.rstrip("m")
    name = name.strip()
    if name not in _NAME_TO_PITCH:
        raise ValueError(f"unknown key name: {text!r}")
    return Key(_NAME_TO_PITCH[name], mode)


ALL_KEYS: list[Key] = [Key(pc, mode) for mode in (MAJOR, MINOR) for pc in range(12)]
