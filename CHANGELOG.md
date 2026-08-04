# Changelog

All notable changes to CueKey are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and versions follow
[Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.8.3] - 2026-08-04

### Fixed
- Deterministic worker segfaults on whole batches of tracks (NULL numba JIT loop pointers): each process now uses a private `NUMBA_CACHE_DIR`, and the build purges stale numba caches so they are never bundled into the DMG. Verified against 24 previously-crashing files at full parallelism.

### Added
- Hard-crash diagnostics: workers and the main process write a Python traceback to `~/Library/Logs/CueKey/crash-<pid>.log` on SIGSEGV-class crashes.
- `CUEKEY_SELFTEST_WORKERS` to control the QA selftest's parallelism.

## [0.8.2] - 2026-08-04

### Fixed
- macOS AppleDouble sidecar files (`._track.mp3`) and other hidden files are no longer picked up as audio when scanning folders.
- The app bundle now carries its real version (crash reports no longer say 0.0.0); the bundle is re-signed after stamping.

### Added
- Files that crash an analysis worker are appended to `~/Library/Logs/CueKey/worker-crashes.log` (and the error row points there), so root causes can be reported and chased.

## [0.8.1] - 2026-08-04

### Fixed
- A crashing worker process (e.g. a corrupt file taking down the native decoder) no longer aborts the whole batch with "the process pool is not usable anymore": the pool is rebuilt automatically, crash suspects are retried one at a time to identify the culprit file (marked with a clear error), and the rest of the batch continues.

### Changed
- Worker processes are recycled every 16 tracks and the worker count is also capped by available RAM, preventing memory-pressure kills on very large batches.
- The completion message now reports analyzed vs failed counts.

## [0.8.0] - 2026-08-01

### Added
- Parallel analysis across CPU cores (process pool, `cores - 2` workers by default; `-j/--jobs` in the CLI). ~3x faster on small batches, more on large libraries.
- Persistent analysis cache (`~/Library/Caches/cuekey`, SQLite) keyed by file path + size + mtime + algorithm version: already-analyzed tracks return instantly; `--no-cache` forces recomputation. Cache entries self-invalidate when files change or detection algorithms are upgraded.

### Changed
- Pause/Cancel now applies to the parallel batch: pause stops new dispatches (running tracks finish), cancel drops queued work and keeps everything already analyzed.

## [0.7.1] - 2026-07-31

### Fixed
- BPM metrical-level errors: trackers locking onto 2/3 of the true tempo on syncopated house tracks (e.g. 80.7 instead of 121) are now corrected by scoring candidate tempos against the onset-envelope autocorrelation at 8 beat-period multiples.
- Key detection on percussion-heavy tracks: chroma is now computed on the harmonic component only (HPSS), fixing whole-tone misdetections caused by kick/percussion smearing.

## [0.7.0] - 2026-07-31

### Added
- Discreet donation button (♥) in the app footer and a "Support the project" help section (Ko-fi + Bitcoin).
- Community files: contributing guide, code of conduct, issue/PR templates, donation info.
- Automated GitHub Releases: pushing a `v*` tag builds the Apple Silicon DMG and publishes it.

### Changed
- License changed from MIT to **PolyForm Noncommercial 1.0.0**: CueKey is free for any noncommercial use; commercial use is not permitted.

## [0.6.1] - 2026-07-31

### Fixed
- The help panel now defaults to the macOS system language (Spanish/English) — `navigator.language` inside WKWebView ignored the system locale. A manual ES/EN choice is remembered.

## [0.6.0] - 2026-07-31

### Added
- Pause/Resume and Cancel controls while an analysis runs. Cancelling the rekordbox flow still saves a partial XML (analyzed tracks kept, the rest untouched).

## [0.5.0] - 2026-07-31

### Added
- In-app help panel (? button) with ES/EN toggle: analysis flows, rekordbox workflow, cue handling, harmonic mixing basics and troubleshooting.

## [0.4.4] - 2026-07-31

### Changed
- "Write tags" and "Hot cues" are now enabled by default in the app.

## [0.4.3] - 2026-07-31

### Fixed
- BPM is re-derived from the tracked beat grid (trimmed mean of inter-beat intervals) and snapped to integer/half values when within 0.2 BPM — steady 128 BPM tracks no longer read as 129.2. Genuinely fractional tempos are kept.

## [0.4.2] - 2026-07-30

### Added
- Live `done / total · %` counter next to the progress bar.

### Fixed
- Progress bar no longer gets stuck below 100%: tracks whose audio file is missing are reported as errors ("file not found") and count toward progress.

## [0.4.1] - 2026-07-30

### Changed
- Existing collection cues are **preserved by default**: CueKey cues are added as extra memory cues (skipping any within 1s of a DJ-made mark) and hot cues only fill free A-H slots. Use `--replace-cues` / the Keep-Replace selector to regenerate from scratch.

## [0.4.0] - 2026-07-30

### Changed
- Desktop app rebuilt as a native WKWebView window with an HTML/CSS/JS interface: interactive harmonic wheel, color-coded key pills, energy bars, cue timeline, MIX WITH suggestions, drag & drop, sortable columns and live filter.

### Added
- App icon (12-segment harmonic wheel), shown in the Dock, Finder and DMG.

## [0.3.0] - 2026-07-30

### Changed
- Dark DJ-oriented theme for the (then Tkinter) GUI, rows tinted by harmonic-wheel position.

## [0.2.0] - 2026-07-30

### Added
- Desktop GUI and macOS DMG packaging (`make dmg`).

## [0.1.0] - 2026-07-30

### Added
- Initial release: key detection (Camelot/Open Key/standard), BPM with octave folding, 1-10 energy heuristic, structural cue points snapped to the beat grid.
- Tag writing (ID3/Vorbis/MP4) and rekordbox XML enrichment (Tonality, AverageBpm, Comments, POSITION_MARK).
- CLI (`cuekey analyze`, `cuekey rekordbox`) and pytest suite with synthesized audio.
