import numpy as np

from cuekey.analysis.key import KRUMHANSL_MAJOR, KRUMHANSL_MINOR, detect_key, detect_key_from_chroma
from tests.conftest import chord


def test_chroma_matching_c_major_profile() -> None:
    result = detect_key_from_chroma(KRUMHANSL_MAJOR.copy())
    assert result.key.standard == "C"
    assert result.confidence > 0


def test_chroma_matching_transposed_minor_profile() -> None:
    # Rotate the minor profile so the tonic lands on A (pitch class 9).
    chroma = np.roll(KRUMHANSL_MINOR, 9)
    result = detect_key_from_chroma(chroma)
    assert result.key.standard == "Am"


def test_detects_c_major_from_audio(sr: int) -> None:
    audio = chord(["C4", "E4", "G4", "C5"], duration_s=10.0, sr=sr)
    result = detect_key(audio, sr)
    assert result.key.standard == "C"


def test_detects_a_minor_from_audio(sr: int) -> None:
    audio = chord(["A3", "C4", "E4", "A4"], duration_s=10.0, sr=sr)
    result = detect_key(audio, sr)
    assert result.key.standard == "Am"
