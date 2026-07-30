"""Write analysis results into audio file tags via mutagen.

Key goes to the format's initial-key field (which rekordbox and other DJ
software read on import), BPM to the tempo field, and a human-readable
summary like '8A - Energy 7' to the comment field.
"""

from __future__ import annotations

from pathlib import Path

from cuekey.models import TrackAnalysis


def write_tags(path: Path, analysis: TrackAnalysis, notation: str = "camelot") -> None:
    suffix = path.suffix.lower()
    key_text = analysis.key.key.standard
    bpm_value = round(analysis.bpm, 2)
    comment = analysis.summary_comment(notation)

    if suffix == ".mp3":
        _write_id3(path, key_text, bpm_value, comment)
    elif suffix in (".aiff", ".aif"):
        _write_aiff(path, key_text, bpm_value, comment)
    elif suffix == ".wav":
        _write_wave(path, key_text, bpm_value, comment)
    elif suffix == ".flac":
        _write_vorbis_flac(path, key_text, bpm_value, comment, analysis.energy)
    elif suffix in (".ogg", ".opus"):
        _write_vorbis_ogg(path, key_text, bpm_value, comment, analysis.energy)
    elif suffix in (".m4a", ".mp4", ".aac"):
        _write_mp4(path, key_text, bpm_value, comment)
    else:
        raise ValueError(f"tag writing not supported for {suffix} files")


def _apply_id3_frames(tags, key_text: str, bpm_value: float, comment: str) -> None:
    from mutagen.id3 import COMM, TBPM, TKEY

    tags.setall("TKEY", [TKEY(encoding=3, text=[key_text])])
    tags.setall("TBPM", [TBPM(encoding=3, text=[f"{bpm_value:g}"])])
    tags.setall("COMM", [COMM(encoding=3, lang="eng", desc="", text=[comment])])


def _write_id3(path: Path, key_text: str, bpm_value: float, comment: str) -> None:
    from mutagen.id3 import ID3, ID3NoHeaderError

    try:
        tags = ID3(str(path))
    except ID3NoHeaderError:
        tags = ID3()
    _apply_id3_frames(tags, key_text, bpm_value, comment)
    tags.save(str(path))


def _write_aiff(path: Path, key_text: str, bpm_value: float, comment: str) -> None:
    from mutagen.aiff import AIFF

    audio = AIFF(str(path))
    if audio.tags is None:
        audio.add_tags()
    _apply_id3_frames(audio.tags, key_text, bpm_value, comment)
    audio.save()


def _write_wave(path: Path, key_text: str, bpm_value: float, comment: str) -> None:
    from mutagen.wave import WAVE

    audio = WAVE(str(path))
    if audio.tags is None:
        audio.add_tags()
    _apply_id3_frames(audio.tags, key_text, bpm_value, comment)
    audio.save()


def _apply_vorbis_fields(audio, key_text: str, bpm_value: float, comment: str, energy: int) -> None:
    audio["INITIALKEY"] = [key_text]
    audio["BPM"] = [f"{bpm_value:g}"]
    audio["COMMENT"] = [comment]
    audio["ENERGYLEVEL"] = [str(energy)]


def _write_vorbis_flac(path: Path, key_text: str, bpm_value: float, comment: str, energy: int) -> None:
    from mutagen.flac import FLAC

    audio = FLAC(str(path))
    _apply_vorbis_fields(audio, key_text, bpm_value, comment, energy)
    audio.save()


def _write_vorbis_ogg(path: Path, key_text: str, bpm_value: float, comment: str, energy: int) -> None:
    import mutagen

    audio = mutagen.File(str(path))
    if audio is None:
        raise ValueError(f"unreadable ogg file: {path}")
    _apply_vorbis_fields(audio, key_text, bpm_value, comment, energy)
    audio.save()


def _write_mp4(path: Path, key_text: str, bpm_value: float, comment: str) -> None:
    from mutagen.mp4 import MP4, MP4FreeForm

    audio = MP4(str(path))
    audio["----:com.apple.iTunes:initialkey"] = [MP4FreeForm(key_text.encode("utf-8"))]
    audio["tmpo"] = [int(round(bpm_value))]
    audio["\xa9cmt"] = [comment]
    audio.save()
