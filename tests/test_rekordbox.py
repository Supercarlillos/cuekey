import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from cuekey.camelot import MINOR, Key
from cuekey.models import CuePoint, KeyResult, TrackAnalysis
from cuekey.rekordbox import RekordboxCollection, enrich_collection


def _location_url(path: Path) -> str:
    return "file://localhost" + urllib.request.pathname2url(str(path))


def _write_collection_xml(xml_path: Path, track_path: Path) -> None:
    xml_path.write_text(
        f"""<?xml version="1.0" encoding="UTF-8"?>
<DJ_PLAYLISTS Version="1.0.0">
  <PRODUCT Name="rekordbox" Version="6.0.0" Company="AlphaTheta"/>
  <COLLECTION Entries="2">
    <TRACK TrackID="1" Name="Synth Groove" Artist="Test"
           Location="{_location_url(track_path)}" TotalTime="30"/>
    <TRACK TrackID="2" Name="Ghost Track"
           Location="file://localhost/nonexistent/dir/missing%20file.mp3"/>
  </COLLECTION>
  <PLAYLISTS>
    <NODE Type="0" Name="ROOT" Count="1">
      <NODE Name="My Set" Type="1" KeyType="0" Entries="1">
        <TRACK Key="1"/>
      </NODE>
    </NODE>
  </PLAYLISTS>
</DJ_PLAYLISTS>
""",
        encoding="utf-8",
    )


def _fake_analysis(path: Path) -> TrackAnalysis:
    return TrackAnalysis(
        path=path,
        duration=180.0,
        bpm=128.0,
        key=KeyResult(key=Key(9, MINOR), confidence=0.9),  # Am / 8A
        energy=7,
        cues=[CuePoint(1.0, "Cue 1"), CuePoint(30.0, "Cue 2")],
    )


@pytest.fixture()
def collection_xml(tmp_path: Path) -> tuple[Path, Path]:
    track = tmp_path / "mi canción.wav"  # non-ASCII + space to exercise URL decoding
    track.write_bytes(b"\x00" * 64)
    xml_path = tmp_path / "collection.xml"
    _write_collection_xml(xml_path, track)
    return xml_path, track


def test_location_url_decoding(collection_xml: tuple[Path, Path]) -> None:
    xml_path, track = collection_xml
    tracks = list(RekordboxCollection.load(xml_path).tracks())
    assert tracks[0].location == track
    assert tracks[1].location == Path("/nonexistent/dir/missing file.mp3")


def test_enrich_sets_key_bpm_comment_and_memory_cues(collection_xml: tuple[Path, Path], tmp_path: Path) -> None:
    xml_path, _ = collection_xml
    out = tmp_path / "out.xml"

    count = enrich_collection(xml_path, out, analyze=_fake_analysis)

    assert count == 1  # the ghost track is skipped, not fatal
    track = ET.parse(out).getroot().find("COLLECTION/TRACK[@TrackID='1']")
    assert track.get("Tonality") == "Am"
    assert track.get("AverageBpm") == "128.00"
    assert track.get("Comments") == "8A - Energy 7"

    marks = track.findall("POSITION_MARK")
    assert [m.get("Num") for m in marks] == ["-1", "-1"]  # memory cues only
    assert [m.get("Start") for m in marks] == ["1.000", "30.000"]


def test_enrich_with_hot_cues(collection_xml: tuple[Path, Path], tmp_path: Path) -> None:
    xml_path, _ = collection_xml
    out = tmp_path / "out.xml"

    enrich_collection(xml_path, out, analyze=_fake_analysis, hot_cues=True)

    track = ET.parse(out).getroot().find("COLLECTION/TRACK[@TrackID='1']")
    nums = sorted(m.get("Num") for m in track.findall("POSITION_MARK"))
    assert nums == ["-1", "-1", "0", "1"]  # memory + hot cues A and B


def test_existing_rekordbox_bpm_is_preserved(collection_xml: tuple[Path, Path], tmp_path: Path) -> None:
    """rekordbox's own BPM drives the DJ's beatgrid: never overwrite it."""
    xml_path, track = collection_xml
    content = xml_path.read_text(encoding="utf-8").replace(
        'TrackID="1" Name="Synth Groove"',
        'TrackID="1" Name="Synth Groove" AverageBpm="180.00"',
    )
    xml_path.write_text(content, encoding="utf-8")
    out = tmp_path / "out.xml"

    enrich_collection(xml_path, out, analyze=_fake_analysis)

    track_el = ET.parse(out).getroot().find("COLLECTION/TRACK[@TrackID='1']")
    assert track_el.get("AverageBpm") == "180.00"  # not our 128.00
    assert track_el.get("Tonality") == "Am"  # key still written


def test_playlist_filter(collection_xml: tuple[Path, Path], tmp_path: Path) -> None:
    xml_path, _ = collection_xml
    collection = RekordboxCollection.load(xml_path)

    in_playlist = collection.tracks_in_playlist("My Set")
    assert [t.track_id for t in in_playlist] == ["1"]

    with pytest.raises(ValueError, match="playlist not found"):
        collection.tracks_in_playlist("Nope")


def _write_collection_with_existing_cues(xml_path: Path, track_path: Path) -> None:
    """Collection whose track already has DJ-made cues: memory at 1.2s and hot cue A at 95s."""
    xml_path.write_text(
        f"""<?xml version="1.0" encoding="UTF-8"?>
<DJ_PLAYLISTS Version="1.0.0">
  <COLLECTION Entries="1">
    <TRACK TrackID="1" Name="Worked Track" Location="{_location_url(track_path)}" TotalTime="30">
      <POSITION_MARK Name="my intro" Type="0" Start="1.200" Num="-1"/>
      <POSITION_MARK Name="my drop" Type="0" Start="95.000" Num="0"/>
    </TRACK>
  </COLLECTION>
</DJ_PLAYLISTS>
""",
        encoding="utf-8",
    )


def test_existing_cues_are_preserved_by_default(collection_xml: tuple[Path, Path], tmp_path: Path) -> None:
    _, track = collection_xml
    xml_path = tmp_path / "worked.xml"
    _write_collection_with_existing_cues(xml_path, track)
    out = tmp_path / "out.xml"

    # Fake analysis cues at 1.0s (within 1s of the DJ's 1.2s mark) and 30.0s.
    enrich_collection(xml_path, out, analyze=_fake_analysis, hot_cues=True)

    track_el = ET.parse(out).getroot().find("COLLECTION/TRACK[@TrackID='1']")
    marks = [(m.get("Name"), m.get("Start"), m.get("Num")) for m in track_el.findall("POSITION_MARK")]

    # The DJ's original marks are untouched.
    assert ("my intro", "1.200", "-1") in marks
    assert ("my drop", "95.000", "0") in marks
    # The 1.0s CueKey cue was skipped (too close to 1.2s); the 30.0s one was
    # added as memory cue plus hot cue in the first free slot (B, since A is taken).
    starts = [m[1] for m in marks]
    assert "1.000" not in starts
    assert ("", "30.000", "-1") in marks
    assert ("", "30.000", "1") in marks
    assert len(marks) == 4


def test_replace_cues_regenerates_everything(collection_xml: tuple[Path, Path], tmp_path: Path) -> None:
    _, track = collection_xml
    xml_path = tmp_path / "worked.xml"
    _write_collection_with_existing_cues(xml_path, track)
    out = tmp_path / "out.xml"

    enrich_collection(xml_path, out, analyze=_fake_analysis, hot_cues=True, replace_cues=True)

    track_el = ET.parse(out).getroot().find("COLLECTION/TRACK[@TrackID='1']")
    marks = [(m.get("Start"), m.get("Num")) for m in track_el.findall("POSITION_MARK")]
    assert marks == [("1.000", "-1"), ("1.000", "0"), ("30.000", "-1"), ("30.000", "1")]


def test_should_stop_saves_partial_result(tmp_path: Path) -> None:
    tracks = []
    for name in ("one.wav", "two.wav"):
        track = tmp_path / name
        track.write_bytes(b"\x00" * 64)
        tracks.append(track)
    xml_path = tmp_path / "two-tracks.xml"
    xml_path.write_text(
        f"""<?xml version="1.0" encoding="UTF-8"?>
<DJ_PLAYLISTS Version="1.0.0">
  <COLLECTION Entries="2">
    <TRACK TrackID="1" Name="One" Location="{_location_url(tracks[0])}"/>
    <TRACK TrackID="2" Name="Two" Location="{_location_url(tracks[1])}"/>
  </COLLECTION>
</DJ_PLAYLISTS>
""",
        encoding="utf-8",
    )
    out = tmp_path / "out.xml"
    done: list[str] = []

    count = enrich_collection(
        xml_path, out, analyze=_fake_analysis,
        on_track=lambda track, analysis, error: done.append(track.name),
        should_stop=lambda: len(done) >= 1,  # cancel after the first track
    )

    assert count == 1
    root = ET.parse(out).getroot()
    assert root.find("COLLECTION/TRACK[@TrackID='1']").get("Tonality") == "Am"
    # The second track was not analyzed but survives untouched in the output.
    assert root.find("COLLECTION/TRACK[@TrackID='2']").get("Tonality") is None


def test_analysis_errors_do_not_abort_batch(collection_xml: tuple[Path, Path], tmp_path: Path) -> None:
    xml_path, _ = collection_xml
    out = tmp_path / "out.xml"
    failures: list[str] = []

    def broken_analyzer(path: Path) -> TrackAnalysis:
        raise RuntimeError("decode failed")

    def on_track(track, analysis, error) -> None:
        if error is not None:
            failures.append(track.name)

    count = enrich_collection(xml_path, out, analyze=broken_analyzer, on_track=on_track)

    assert count == 0
    # Both the failed analysis and the missing file are reported, so
    # progress counters always reach the total (order is not guaranteed).
    assert sorted(failures) == ["Ghost Track", "Synth Groove"]
    assert out.exists()
