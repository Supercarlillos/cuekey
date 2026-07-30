# CueKey

**Open-source DJ track analysis for harmonic mixing.** CueKey analyzes your music library and detects, for every track:

- 🎹 **Musical key**, in standard (`Am`), Camelot-style wheel (`8A`) or Open Key (`1m`) notation
- 🥁 **BPM** (tempo), with octave-error correction
- ⚡ **Energy level** from 1 to 10, to plan the intensity curve of your sets
- 📍 **Automatic cue points** (up to 8) at structural boundaries, snapped to the beat grid

Results can be written to your audio file tags and to a **rekordbox XML collection**, so key, BPM, energy and cue points show up directly in rekordbox.

> CueKey is an independent open-source project. It is not affiliated with, endorsed by, or derived from any commercial DJ software. "rekordbox" is a trademark of AlphaTheta Corporation, used here only to describe interoperability.

## Requirements (macOS)

- macOS 12+ (Apple Silicon or Intel)
- Python 3.11+ (`brew install python@3.13`)
- ffmpeg for exotic formats (optional but recommended): `brew install ffmpeg`

Supported formats: MP3, M4A/AAC, FLAC, WAV, AIFF, OGG.

## Install

### Desktop app (DMG)

Build (or download from Releases, once published) the standalone app — no Python required on the target Mac:

```bash
make dev && make dmg          # produces dist/CueKey-<version>.dmg
```

Open the DMG and drag **CueKey.app** to Applications. The build is not code-signed/notarized, so on first launch right-click the app and choose **Open** (or run `xattr -dr com.apple.quarantine /Applications/CueKey.app`).

The app lets you add files or a folder (or pick a rekordbox XML), shows key/BPM/energy/cues per track with progress, and can write file tags and enriched XML — same engine as the CLI.

### CLI

The recommended way on macOS is [pipx](https://pipx.pypa.io):

```bash
brew install pipx ffmpeg
pipx install cuekey            # from PyPI (when published)
# or, from a clone of this repo:
pipx install .
```

For development:

```bash
git clone https://github.com/<you>/cuekey && cd cuekey
python3.13 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

## Usage

### Analyze files or folders

```bash
cuekey analyze ~/Music/DJ/           # prints key, BPM, energy per track
cuekey analyze track.mp3 --json      # machine-readable output
cuekey analyze ~/Music/DJ/ --tags    # also writes results into file tags
cuekey analyze track.mp3 --notation camelot
```

`--tags` writes:

| Field | MP3 (ID3) | FLAC/OGG | M4A |
|---|---|---|---|
| Key | `TKEY` | `INITIALKEY` | `initialkey` |
| BPM | `TBPM` | `BPM` | `tmpo` |
| Energy + key | `COMM` comment (`8A - Energy 7`) | `COMMENT` | `©cmt` |

The comment format (`8A - Energy 7`) is readable in any DJ software's comment column.

### rekordbox workflow

1. In rekordbox: `File → Export Collection in xml format` (or use the auto-exported `rekordbox.xml`).
2. Analyze it:

   ```bash
   cuekey rekordbox collection.xml -o cuekey.xml
   cuekey rekordbox collection.xml -o cuekey.xml --playlist "My Set"   # only one playlist
   cuekey rekordbox collection.xml -o cuekey.xml --hot-cues            # hot cues A-H too
   ```

3. In rekordbox: `Preferences → Advanced → Database → rekordbox xml → Imported Library`, point it to `cuekey.xml`.
4. The **rekordbox xml** node now shows your tracks with key (`Tonality`), BPM, energy (in comments) and cue points (memory cues, plus hot cues with `--hot-cues`). Drag tracks/playlists into your collection to import them.

### Harmonic mixing in 10 seconds

Mix between tracks whose wheel numbers are equal or adjacent, keeping the same letter (`8A → 8A, 7A, 9A`), or switch letter at the same number (`8A → 8B`) to move between minor and major. Use energy levels to build or release intensity across your set.

## How it works

- **Key**: chroma (pitch-class) distribution of the whole track correlated against the 24 Krumhansl-Kessler major/minor key profiles (classic music-cognition research data).
- **BPM**: onset-envelope beat tracking (librosa), folded into the 70-180 BPM range to avoid half/double-tempo errors.
- **Energy**: a 1-10 heuristic combining perceived loudness (RMS), onset density, low-frequency (bass) ratio and tempo.
- **Cue points**: structural segmentation over timbre+harmony features (agglomerative clustering), boundaries snapped to the nearest downbeat.

## Roadmap

- [x] macOS app bundle + DMG (Tkinter GUI, PyInstaller)
- [ ] Code signing & notarization for the DMG
- [ ] Direct `master.db` reading (rekordbox 6/7) via pyrekordbox
- [ ] Homebrew tap (`brew install cuekey`)
- [ ] Serato / Traktor / Engine DJ export

## License

[MIT](LICENSE). Contributions welcome.
