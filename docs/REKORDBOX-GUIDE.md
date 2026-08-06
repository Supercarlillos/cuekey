# Guide: using CueKey with rekordbox

> 🇪🇸 [Versión en español](GUIA-REKORDBOX.md)

## How it works (the concept)

rekordbox stores your collection in an internal database (`master.db`) that
no external application can modify. The official bridge rekordbox offers for
exchanging data is its **XML format**: a text file containing the list of
your tracks (with the path to each audio file, BPM, key, cue points…) and
your playlists.

CueKey uses that bridge. **It never touches your real collection**: it reads
the XML you export, locates each audio file on disk, analyzes the audio
itself (key, BPM, energy, cue points) and writes an **enriched copy** of the
XML. rekordbox then imports that copy.

```
┌───────────┐  1. Export XML     ┌──────────┐  2. Analyze audio   ┌───────────────┐
│ rekordbox │ ─────────────────▶ │  CueKey  │ ──────────────────▶ │ enriched XML  │
└───────────┘                    └──────────┘                     └───────┬───────┘
      ▲                                                                   │
      └────────────────── 3. Import into rekordbox ◀──────────────────────┘
```

What CueKey adds to each track in the XML:

| XML field | What it is | Where you see it in rekordbox |
|---|---|---|
| `Tonality` | Detected key (`Am`) | **Key** column |
| `AverageBpm` | Detected BPM — **only if rekordbox hasn't analyzed the track yet** (your beatgrid is never contradicted) | **BPM** column |
| `Comments` | `8A - Energy 7` | **Comments** column |
| `POSITION_MARK` | Cue points | Memory cues (and hot cues A-H with `--hot-cues`) |

## Step 1 — Export your collection from rekordbox

1. Open rekordbox (Export mode).
2. Menu **File → Export Collection in xml format**.
3. Save it anywhere, e.g. `~/Desktop/collection.xml`.

That file contains *references* to your tracks, not the audio: your music
files are neither copied nor modified.

## Step 2 — Analyze with CueKey

### With the app (DMG)

1. Open **CueKey.app**.
2. (Optional) pick the notation (`camelot` = `8A`), and enable *Hot cues
   (XML)* if you want hot cues A-H in addition to memory cues.
3. Press **rekordbox XML…**, choose your `collection.xml` and the output
   file name (default `collection-cuekey.xml`).
4. The whole collection appears in the table immediately; each row fills in
   with key, BPM, energy and cue count as its analysis completes.

### With the CLI

```bash
cuekey rekordbox ~/Desktop/collection.xml -o ~/Desktop/collection-cuekey.xml

# A single playlist (much faster for a trial run):
cuekey rekordbox collection.xml -o out.xml --playlist "My Set"

# With hot cues, also writing file tags:
cuekey rekordbox collection.xml -o out.xml --hot-cues --tags

# Quick trial with the first 5 tracks:
cuekey rekordbox collection.xml -o out.xml --limit 5
```

Analysis runs in parallel across your CPU cores (~2-5 seconds per track) and
results are cached: re-running only computes new or changed files — already
analyzed tracks return instantly. Tracks whose file cannot be found on disk
are reported (⚠ errors panel in the app) without stopping the batch.

## Step 3 — Import the result into rekordbox

1. **Preferences → Advanced → Database tab → rekordbox xml**: under
   *Imported Library* select your `collection-cuekey.xml`.
2. **Preferences → View → Layout**: tick the **rekordbox xml** checkbox so
   it shows up in the sidebar.
3. The sidebar now shows a **rekordbox xml** node with your tracks and
   playlists, already displaying Key, BPM and comments.
4. To bring the data into your real collection, **drag tracks (or whole
   playlists) from the rekordbox xml node into your Collection**.

## What happens to my existing cues?

**They are respected by default.** If your collection already has hot cues
or memory cues:

- Your original marks are preserved untouched in the enriched XML.
- CueKey's cues are added as *extra* memory cues, skipping any that land
  within 1 second of one of your marks (no duplicates).
- With hot cues enabled, CueKey only fills the **free slots** (if you
  already use hot cue A, its first cue goes to B, and so on).
- Prefer a clean regeneration? `--replace-cues` in the CLI, or the
  **Existing cues: Keep / Replace** selector in the app.

## Important notes

- ⚠️ **When you drag a track from the XML, rekordbox replaces its info with
  the XML's** (that is rekordbox behavior, not CueKey's). Since CueKey's XML
  preserves your cues and your rekordbox BPM by default, nothing is lost —
  but with *Replace* only the generated cues would remain. Try a small
  playlist first.
- **Your rekordbox BPM and beatgrid are never contradicted**: if rekordbox
  already analyzed a track, its `AverageBpm` is kept as-is; CueKey's BPM is
  only written for tracks rekordbox hasn't analyzed yet.
- The enriched XML is a new file: your original `collection.xml` and your
  rekordbox database stay intact until you drag something.
- **No-XML alternative**: `cuekey analyze ~/Music/DJ --tags` writes key, BPM
  and the `8A - Energy 7` comment straight into the file tags; rekordbox
  reads them when you reload/reanalyze the track. Note that **cue points can
  only travel via XML** — tags cannot carry them.
- Pick the notation with `--notation camelot|openkey|standard`. rekordbox
  shows the `Tonality` text as-is in the Key column (`Am` by default; the
  `8A` lives in the comment).

## Harmonic mixing in 10 seconds

On the harmonic wheel (`8A`, `9B`…): mix between tracks with the **same or
adjacent number keeping the letter** (`8A → 7A/8A/9A`), or **swap the letter
at the same number** (`8A → 8B`) to move between minor and major. Use the
1-10 energy level to plan intensity rises and drops across your set.
