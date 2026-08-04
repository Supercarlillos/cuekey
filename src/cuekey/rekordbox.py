"""rekordbox XML collection (DJ_PLAYLISTS format) reading and enrichment.

The workflow is: export the collection (or a playlist) from rekordbox as
XML, run the analysis, and import the enriched XML back through
Preferences > Advanced > Database > rekordbox xml.

Per track we set:
- Tonality  -> detected key
- AverageBpm -> detected BPM
- Comments  -> '8A - Energy 7' style summary
- POSITION_MARK children -> memory cues (Num=-1) and optionally hot cues (Num=0..7)
"""

from __future__ import annotations

import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterator

from cuekey.models import TrackAnalysis


@dataclass
class RekordboxTrack:
    element: ET.Element

    @property
    def track_id(self) -> str:
        return self.element.get("TrackID", "")

    @property
    def name(self) -> str:
        return self.element.get("Name", "")

    @property
    def location(self) -> Path | None:
        """Decode the Location attribute (file://localhost/... URL) to a path."""
        url = self.element.get("Location", "")
        if not url.startswith("file://"):
            return None
        parsed = urllib.parse.urlparse(url)
        return Path(urllib.request.url2pathname(parsed.path))

    def apply(
        self,
        analysis: TrackAnalysis,
        notation: str,
        hot_cues: bool,
        replace_cues: bool = False,
    ) -> None:
        """Write analysis results into the TRACK element.

        Existing POSITION_MARKs (the DJ's own cues) are preserved by default:
        CueKey cues are added as extra memory cues, skipping any that land
        within 1 second of an existing mark, and hot cues only fill free A-H
        slots. With replace_cues=True all existing marks are regenerated.
        """
        self.element.set("Tonality", analysis.key.key.standard)
        # rekordbox's own BPM drives the DJ's beatgrid — never contradict it.
        # Ours is only written when rekordbox hasn't analyzed the track yet.
        if not self.element.get("AverageBpm"):
            self.element.set("AverageBpm", f"{analysis.bpm:.2f}")
        self.element.set("Comments", analysis.summary_comment(notation))

        if replace_cues:
            for mark in self.element.findall("POSITION_MARK"):
                self.element.remove(mark)
        existing = self.element.findall("POSITION_MARK")
        existing_starts = [float(m.get("Start", "0")) for m in existing]
        used_slots = {int(m.get("Num", "-1")) for m in existing}
        free_slots = iter(n for n in range(8) if n not in used_slots)

        for cue in analysis.cues:
            if any(abs(cue.seconds - start) < 1.0 for start in existing_starts):
                continue  # the DJ already marked this spot — respect it
            self._add_position_mark(cue.seconds, num=-1)  # memory cue
            if hot_cues:
                slot = next(free_slots, None)
                if slot is not None:
                    self._add_position_mark(cue.seconds, num=slot)
        self.element.set("TotalTime", self.element.get("TotalTime") or str(int(analysis.duration)))

    def _add_position_mark(self, seconds: float, num: int) -> None:
        ET.SubElement(
            self.element,
            "POSITION_MARK",
            {"Name": "", "Type": "0", "Start": f"{seconds:.3f}", "Num": str(num)},
        )


class RekordboxCollection:
    def __init__(self, tree: ET.ElementTree):
        self._tree = tree
        root = tree.getroot()
        if root.tag != "DJ_PLAYLISTS":
            raise ValueError("not a rekordbox XML collection (missing DJ_PLAYLISTS root)")
        collection = root.find("COLLECTION")
        if collection is None:
            raise ValueError("rekordbox XML has no COLLECTION element")
        self._collection = collection
        self._playlists_root = root.find("PLAYLISTS")

    @classmethod
    def load(cls, path: Path) -> "RekordboxCollection":
        return cls(ET.parse(str(path)))

    def tracks(self) -> Iterator[RekordboxTrack]:
        for element in self._collection.findall("TRACK"):
            yield RekordboxTrack(element)

    def playlist_track_ids(self, playlist_name: str) -> set[str]:
        """TrackIDs referenced by the playlist NODE with the given name."""
        if self._playlists_root is None:
            raise ValueError("rekordbox XML has no PLAYLISTS section")
        for node in self._playlists_root.iter("NODE"):
            if node.get("Name") == playlist_name and node.get("Type") == "1":
                return {t.get("Key", "") for t in node.findall("TRACK")}
        raise ValueError(f"playlist not found: {playlist_name!r}")

    def tracks_in_playlist(self, playlist_name: str | None) -> list[RekordboxTrack]:
        if playlist_name is None:
            return list(self.tracks())
        ids = self.playlist_track_ids(playlist_name)
        return [t for t in self.tracks() if t.track_id in ids]

    def save(self, path: Path) -> None:
        ET.indent(self._tree, space="  ")
        self._tree.write(str(path), encoding="UTF-8", xml_declaration=True)


def enrich_collection(
    xml_in: Path,
    xml_out: Path,
    analyze: Callable[[Path], TrackAnalysis] | None = None,
    playlist: str | None = None,
    notation: str = "camelot",
    hot_cues: bool = False,
    replace_cues: bool = False,
    limit: int | None = None,
    on_track: Callable[[RekordboxTrack, TrackAnalysis | None, Exception | None], None] | None = None,
    should_stop: Callable[[], bool] | None = None,
    max_workers: int | None = None,
    use_cache: bool = True,
) -> int:
    """Analyze every locatable track and write the enriched XML. Returns count.

    With analyze=None (the default) files are analyzed cache-aware and in
    parallel across CPU cores; passing a callable forces a sequential run
    with that analyzer (used by tests). should_stop is polled between
    tracks (and may block while paused); on stop the XML is still written,
    keeping whatever was enriched so far.
    """
    collection = RekordboxCollection.load(xml_in)

    pending: list[tuple[RekordboxTrack, Path]] = []
    for track in collection.tracks_in_playlist(playlist):
        if limit is not None and len(pending) >= limit:
            break
        location = track.location
        if location is None or not location.exists():
            if on_track:  # report so progress counters stay accurate
                on_track(track, None, FileNotFoundError(f"file not found: {location}"))
            continue
        pending.append((track, location))

    processed = 0

    def apply_result(track: RekordboxTrack, analysis: TrackAnalysis | None,
                     error: Exception | None) -> None:
        nonlocal processed
        if error is not None or analysis is None:
            if on_track:
                on_track(track, None, error)
            return
        track.apply(analysis, notation=notation, hot_cues=hot_cues, replace_cues=replace_cues)
        processed += 1
        if on_track:
            on_track(track, analysis, None)

    if analyze is not None:
        for track, location in pending:
            if should_stop is not None and should_stop():
                break
            try:
                apply_result(track, analyze(location), None)
            except Exception as error:  # one bad file must not kill the batch
                apply_result(track, None, error)
    else:
        from cuekey.analyzer import analyze_many

        tracks_by_path: dict[Path, list[RekordboxTrack]] = {}
        for track, location in pending:
            tracks_by_path.setdefault(location, []).append(track)

        def on_result(path: Path, analysis: TrackAnalysis | None,
                      error: Exception | None) -> None:
            for track in tracks_by_path[path]:
                apply_result(track, analysis, error)

        analyze_many(
            list(tracks_by_path), on_result,
            max_workers=max_workers, use_cache=use_cache, should_stop=should_stop,
        )

    collection.save(xml_out)
    return processed
