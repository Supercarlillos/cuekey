# Changelog

All notable changes to CueKey are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and versions follow
[Semantic Versioning](https://semver.org/).

## [Unreleased]

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
