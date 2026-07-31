"""CueKey desktop app: native WKWebView window (pywebview) over an
HTML/CSS/JS interface, backed by the same analysis engine as the CLI.

The JS side calls methods on the Api class (window.pywebview.api.*);
Python pushes analysis events back with window.evaluate_js(). Analysis
runs on worker threads so the UI stays responsive.
"""

from __future__ import annotations

import json
import os
import sys
import threading
import time
from pathlib import Path

import webview

from cuekey import __version__
from cuekey.audio import SUPPORTED_EXTENSIONS, is_supported
from cuekey.models import TrackAnalysis

WINDOW_TITLE = "CueKey"

_FILE_DIALOG_TYPES = (
    "Audio files (*.mp3;*.m4a;*.aac;*.flac;*.wav;*.aiff;*.aif;*.ogg;*.opus)",
    "All files (*.*)",
)


def ui_dir() -> Path:
    if getattr(sys, "frozen", False):  # PyInstaller bundle
        return Path(sys._MEIPASS) / "cuekey" / "ui"
    return Path(__file__).parent / "ui"


def system_language() -> str:
    """Two-letter system language ('es', 'en', ...).

    Finder-launched apps don't inherit LANG and WKWebView reports its own
    navigator.language, so ask macOS directly via NSLocale.
    """
    try:
        from Foundation import NSLocale  # provided by pywebview's pyobjc deps

        preferred = NSLocale.preferredLanguages()
        if preferred:
            return str(preferred[0])[:2].lower()
    except Exception:
        pass
    import locale

    lang = locale.getlocale()[0] or os.environ.get("LANG", "en")
    return (lang or "en")[:2].lower()


def _track_payload(analysis: TrackAnalysis, track_id: str, name: str) -> dict:
    key = analysis.key.key
    return {
        "id": track_id,
        "name": name,
        "path": str(analysis.path),
        "standard": key.standard,
        "camelot": key.camelot,
        "openkey": key.openkey,
        "wheel": key.wheel_number,
        "mode": key.mode,
        "bpm": round(analysis.bpm, 2),
        "energy": analysis.energy,
        "cues": [round(c.seconds, 3) for c in analysis.cues],
        "duration": round(analysis.duration, 2),
    }


class Api:
    """Methods exposed to JavaScript as window.pywebview.api.*"""

    def __init__(self) -> None:
        self.window: webview.Window | None = None
        self.queued: dict[str, Path] = {}  # track id -> audio path
        self._worker: threading.Thread | None = None
        self._lock = threading.Lock()
        self._cancel = threading.Event()
        self._paused = threading.Event()

    # ------------------------------------------------------------ plumbing

    def _emit(self, event: dict) -> None:
        if self.window is not None:
            self.window.evaluate_js(f"CueKey.onEvent({json.dumps(event)})")

    def _start_worker(self, target, *args) -> bool:
        with self._lock:
            if self._worker is not None and self._worker.is_alive():
                return False
            self._cancel.clear()
            self._paused.clear()
            self._worker = threading.Thread(target=target, args=args, daemon=True)
            self._worker.start()
            return True

    def _stopped(self) -> bool:
        """Poll point for workers: blocks while paused, True once cancelled."""
        while self._paused.is_set() and not self._cancel.is_set():
            time.sleep(0.2)
        return self._cancel.is_set()

    # ------------------------------------------------------ analysis control

    def pause_analysis(self) -> None:
        self._paused.set()
        self._emit({"type": "status", "message": "Paused — finishing the current track first."})

    def resume_analysis(self) -> None:
        self._paused.clear()
        self._emit({"type": "status", "message": "Resumed."})

    def cancel_analysis(self) -> None:
        self._cancel.set()
        self._paused.clear()  # unblock a paused worker so it can exit

    # ------------------------------------------------------------- queueing

    def app_info(self) -> dict:
        return {"version": __version__, "language": system_language()}

    def pick_files(self) -> None:
        picked = self.window.create_file_dialog(
            webview.OPEN_DIALOG, allow_multiple=True, file_types=_FILE_DIALOG_TYPES
        )
        self.queue_paths(list(picked or []))

    def pick_folder(self) -> None:
        picked = self.window.create_file_dialog(webview.FOLDER_DIALOG)
        if picked:
            self.queue_paths([picked[0]])

    def queue_paths(self, paths: list[str]) -> None:
        """Add files (or folders, recursively) to the analysis queue."""
        added = []
        for raw in paths:
            path = Path(raw)
            candidates = (
                sorted(p for p in path.rglob("*") if p.is_file()) if path.is_dir() else [path]
            )
            for file in candidates:
                if not is_supported(file) or file in self.queued.values():
                    continue
                track_id = f"t{len(self.queued)}"
                self.queued[track_id] = file
                added.append({"id": track_id, "name": file.name, "path": str(file)})
        if added:
            self._emit({"type": "queued", "tracks": added})
        else:
            extensions = ", ".join(sorted(SUPPORTED_EXTENSIONS))
            self._emit({"type": "status", "message": f"No new audio files found ({extensions})."})

    # ------------------------------------------------------------- analysis

    def analyze(self, track_ids: list[str], options: dict) -> bool:
        pending = [(tid, self.queued[tid]) for tid in track_ids if tid in self.queued]
        return self._start_worker(self._analyze_worker, pending, options)

    def _analyze_worker(self, pending: list[tuple[str, Path]], options: dict) -> None:
        from cuekey.analyzer import analyze_file
        from cuekey.tagging import write_tags

        analyzed = 0
        for track_id, path in pending:
            if self._stopped():
                self._emit({"type": "done",
                            "message": f"Cancelled — {analyzed} of {len(pending)} tracks analyzed."})
                return
            try:
                analysis = analyze_file(path)
                if options.get("write_tags"):
                    write_tags(path, analysis, notation=options.get("notation", "camelot"))
                self._emit({"type": "row", "track": _track_payload(analysis, track_id, path.name)})
            except Exception as error:
                self._emit({
                    "type": "row_error", "id": track_id, "name": path.name, "message": str(error),
                })
            analyzed += 1
        self._emit({"type": "done", "message": f"Analyzed {len(pending)} tracks."})

    # ------------------------------------------------------------ rekordbox

    def enrich_rekordbox(self, options: dict) -> bool:
        xml_in = self.window.create_file_dialog(
            webview.OPEN_DIALOG, file_types=("rekordbox XML (*.xml)",)
        )
        if not xml_in:
            return False
        xml_in_path = Path(xml_in[0])
        xml_out = self.window.create_file_dialog(
            webview.SAVE_DIALOG,
            save_filename=f"{xml_in_path.stem}-cuekey.xml",
            directory=str(xml_in_path.parent),
        )
        if not xml_out:
            return False
        xml_out_path = Path(xml_out if isinstance(xml_out, str) else xml_out[0])
        return self._start_worker(self._rekordbox_worker, xml_in_path, xml_out_path, options)

    def _rekordbox_worker(self, xml_in: Path, xml_out: Path, options: dict) -> None:
        from cuekey.analyzer import analyze_file
        from cuekey.rekordbox import RekordboxCollection, enrich_collection
        from cuekey.tagging import write_tags

        notation = options.get("notation", "camelot")
        try:
            total = len(RekordboxCollection.load(xml_in).tracks_in_playlist(None))
            self._emit({"type": "total", "total": total,
                        "message": f"Analyzing {total} tracks from {xml_in.name}…"})
            counter = iter(range(1_000_000))

            def on_track(track, analysis, error) -> None:
                if error is not None:
                    self._emit({"type": "row_error", "id": f"x{next(counter)}",
                                "name": track.name, "message": str(error)})
                    return
                if options.get("write_tags") and analysis is not None:
                    try:
                        write_tags(analysis.path, analysis, notation=notation)
                    except Exception:
                        pass  # tag failures must not stop the batch
                self._emit({"type": "row",
                            "track": _track_payload(analysis, f"x{next(counter)}", track.name)})

            count = enrich_collection(
                xml_in, xml_out, analyze=analyze_file,
                notation=notation, hot_cues=bool(options.get("hot_cues")),
                replace_cues=bool(options.get("replace_cues")), on_track=on_track,
                should_stop=self._stopped,
            )
            if self._cancel.is_set():
                self._emit({"type": "done",
                            "message": f"Cancelled — the {count} tracks already analyzed were "
                                       f"saved to {xml_out.name}; the rest stay unchanged."})
            else:
                self._emit({"type": "done",
                            "message": f"{count} tracks analyzed → {xml_out.name}. Import it via "
                                       "rekordbox Preferences → Advanced → Database → rekordbox xml."})
        except Exception as error:
            self._emit({"type": "fatal", "message": str(error)})


def _demo_payloads() -> list[dict]:
    """Sample rows for design review/screenshots (CUEKEY_DEMO=1)."""
    from cuekey.camelot import parse_key
    from cuekey.models import CuePoint, KeyResult

    demo = [
        ("Midnight Circuit.mp3", "Am", 124.0, 6, [15.5, 45.2, 92.1, 140.0, 210.3]),
        ("Neon Harbor.wav", "F#m", 128.0, 8, [12.0, 60.4, 120.8, 181.2]),
        ("Glass Meridian.flac", "C", 122.3, 5, [30.1, 95.6, 160.2]),
        ("Ember Static.mp3", "Gm", 126.0, 9, [8.2, 40.9, 88.4, 133.0, 200.5, 245.1]),
        ("Vapor Lane.m4a", "Ebm", 174.0, 10, [16.5, 65.3, 131.0, 196.6]),
        ("Quiet Antenna.aiff", "D", 118.7, 3, [22.4, 110.9]),
        ("Copper Skyline.mp3", "Bm", 125.5, 7, [14.8, 74.2, 148.5, 222.7]),
        ("Low Tide Signal.flac", "Fm", 121.0, 4, [28.0, 84.3, 168.9]),
    ]
    payloads = []
    for index, (name, key, bpm, energy, cues) in enumerate(demo):
        analysis = TrackAnalysis(
            path=Path("/Music") / name, duration=372.0, bpm=bpm,
            key=KeyResult(parse_key(key), 0.8), energy=energy,
            cues=[CuePoint(c) for c in cues],
        )
        payloads.append(_track_payload(analysis, f"demo{index}", name))
    return payloads


def main() -> None:
    api = Api()
    window = webview.create_window(
        WINDOW_TITLE,
        url=str(ui_dir() / "index.html"),
        js_api=api,
        width=1080,
        height=720,
        min_size=(880, 600),
        background_color="#0b0c10",
    )
    api.window = window

    def on_start() -> None:
        if os.environ.get("CUEKEY_DEMO"):
            time.sleep(0.6)  # let the DOM finish loading
            for payload in _demo_payloads():
                api._emit({"type": "row", "track": payload})
            api._emit({"type": "done", "message": "8 tracks analyzed (demo data)."})
        if os.environ.get("CUEKEY_SMOKE"):
            time.sleep(1.5)
            window.destroy()

    webview.start(on_start)


if __name__ == "__main__":
    main()
