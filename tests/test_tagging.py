from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from cuekey.camelot import MINOR, Key
from cuekey.models import CuePoint, KeyResult, TrackAnalysis
from cuekey.tagging import write_tags


def _analysis(path: Path) -> TrackAnalysis:
    return TrackAnalysis(
        path=path,
        duration=10.0,
        bpm=128.0,
        key=KeyResult(key=Key(9, MINOR), confidence=0.9),  # Am / 8A
        energy=7,
        cues=[CuePoint(1.0)],
    )


def _write_audio(path: Path, fmt: str) -> None:
    tone = (0.2 * np.sin(2 * np.pi * 440 * np.arange(22050) / 22050)).astype(np.float32)
    sf.write(str(path), tone, 22050, format=fmt)


def test_writes_id3_tags_to_wav(tmp_path: Path) -> None:
    from mutagen.wave import WAVE

    path = tmp_path / "track.wav"
    _write_audio(path, "WAV")

    write_tags(path, _analysis(path))

    tags = WAVE(str(path)).tags
    assert str(tags["TKEY"]) == "Am"
    assert str(tags["TBPM"]) == "128"
    assert "8A - Energy 7" in str(tags.getall("COMM")[0])


def test_writes_vorbis_tags_to_flac(tmp_path: Path) -> None:
    from mutagen.flac import FLAC

    path = tmp_path / "track.flac"
    _write_audio(path, "FLAC")

    write_tags(path, _analysis(path))

    audio = FLAC(str(path))
    assert audio["INITIALKEY"] == ["Am"]
    assert audio["BPM"] == ["128"]
    assert audio["COMMENT"] == ["8A - Energy 7"]
    assert audio["ENERGYLEVEL"] == ["7"]


def test_writes_id3_tags_to_aiff(tmp_path: Path) -> None:
    from mutagen.aiff import AIFF

    path = tmp_path / "track.aiff"
    _write_audio(path, "AIFF")

    write_tags(path, _analysis(path))

    tags = AIFF(str(path)).tags
    assert str(tags["TKEY"]) == "Am"


def test_unsupported_extension_rejected(tmp_path: Path) -> None:
    path = tmp_path / "track.xyz"
    path.write_bytes(b"")
    with pytest.raises(ValueError, match="not supported"):
        write_tags(path, _analysis(path))
