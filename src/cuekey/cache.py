"""Persistent analysis-result cache.

Results are stored in a small SQLite database (default:
~/Library/Caches/cuekey/analysis.sqlite, override with CUEKEY_CACHE_DIR)
keyed by absolute file path and validated by file size, modification time
and the analysis algorithm version — editing a file or upgrading the
detector invalidates its entry automatically.
"""

from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

from cuekey.camelot import Key
from cuekey.models import CuePoint, KeyResult, TrackAnalysis

# Bump when detection algorithms change so stale results are recomputed.
# 1: initial release · 2: BPM grid refinement · 3: HPSS key + metrical re-leveling
ANALYSIS_VERSION = 3


def default_cache_path() -> Path:
    base = os.environ.get("CUEKEY_CACHE_DIR")
    directory = Path(base) if base else Path.home() / "Library" / "Caches" / "cuekey"
    directory.mkdir(parents=True, exist_ok=True)
    return directory / "analysis.sqlite"


def _to_payload(analysis: TrackAnalysis) -> str:
    return json.dumps({
        "duration": analysis.duration,
        "bpm": analysis.bpm,
        "pitch_class": analysis.key.key.pitch_class,
        "mode": analysis.key.key.mode,
        "confidence": analysis.key.confidence,
        "energy": analysis.energy,
        "cues": [[c.seconds, c.label] for c in analysis.cues],
    })


def _from_payload(path: Path, payload: str) -> TrackAnalysis:
    data = json.loads(payload)
    return TrackAnalysis(
        path=path,
        duration=data["duration"],
        bpm=data["bpm"],
        key=KeyResult(
            key=Key(data["pitch_class"], data["mode"]),
            confidence=data["confidence"],
        ),
        energy=data["energy"],
        cues=[CuePoint(seconds, label) for seconds, label in data["cues"]],
    )


class AnalysisCache:
    def __init__(self, db_path: Path | None = None):
        self._conn = sqlite3.connect(str(db_path or default_cache_path()))
        self._conn.execute(
            """CREATE TABLE IF NOT EXISTS analysis (
                path TEXT PRIMARY KEY,
                size INTEGER NOT NULL,
                mtime_ns INTEGER NOT NULL,
                version INTEGER NOT NULL,
                has_cues INTEGER NOT NULL,
                payload TEXT NOT NULL
            )"""
        )
        self._conn.commit()

    def get(self, path: Path, require_cues: bool = True) -> TrackAnalysis | None:
        try:
            stat = path.stat()
        except OSError:
            return None
        row = self._conn.execute(
            "SELECT size, mtime_ns, version, has_cues, payload FROM analysis WHERE path = ?",
            (str(path),),
        ).fetchone()
        if row is None:
            return None
        size, mtime_ns, version, has_cues, payload = row
        if size != stat.st_size or mtime_ns != stat.st_mtime_ns or version != ANALYSIS_VERSION:
            return None
        if require_cues and not has_cues:
            return None
        try:
            return _from_payload(path, payload)
        except (KeyError, ValueError, json.JSONDecodeError):
            return None

    def put(self, path: Path, analysis: TrackAnalysis, has_cues: bool = True) -> None:
        try:
            stat = path.stat()
        except OSError:
            return
        self._conn.execute(
            "INSERT OR REPLACE INTO analysis (path, size, mtime_ns, version, has_cues, payload)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (str(path), stat.st_size, stat.st_mtime_ns, ANALYSIS_VERSION,
             int(has_cues), _to_payload(analysis)),
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()
