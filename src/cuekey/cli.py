"""CueKey command-line interface."""

from __future__ import annotations

import json
from pathlib import Path

import click
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table

from cuekey import __version__
from cuekey.audio import is_supported

console = Console()

NOTATIONS = ("camelot", "standard", "openkey")


def _collect_audio_files(paths: tuple[Path, ...]) -> list[Path]:
    files: list[Path] = []
    for path in paths:
        if path.is_dir():
            files.extend(p for p in sorted(path.rglob("*")) if p.is_file() and is_supported(p))
        elif path.is_file() and is_supported(path):
            files.append(path)
    return files


def _progress() -> Progress:
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        TimeElapsedColumn(),
        console=console,
    )


@click.group()
@click.version_option(version=__version__, prog_name="cuekey")
def main() -> None:
    """Open-source DJ track analysis: key, BPM, energy and cue points."""


@main.command()
@click.argument("paths", nargs=-1, required=True, type=click.Path(exists=True, path_type=Path))
@click.option("--notation", type=click.Choice(NOTATIONS), default="camelot", show_default=True)
@click.option("--tags", is_flag=True, help="Write results into the audio file tags.")
@click.option("--json", "as_json", is_flag=True, help="Output JSON instead of a table.")
@click.option("--no-cues", is_flag=True, help="Skip cue point detection (faster).")
def analyze(paths: tuple[Path, ...], notation: str, tags: bool, as_json: bool, no_cues: bool) -> None:
    """Analyze audio files or folders."""
    from cuekey.analyzer import analyze_file
    from cuekey.tagging import write_tags

    files = _collect_audio_files(paths)
    if not files:
        raise click.ClickException("no supported audio files found")

    results = []
    errors: list[tuple[Path, str]] = []
    with _progress() as progress:
        task = progress.add_task("Analyzing", total=len(files))
        for file in files:
            progress.update(task, description=f"Analyzing {file.name[:40]}")
            try:
                analysis = analyze_file(file, with_cues=not no_cues)
                if tags:
                    write_tags(file, analysis, notation=notation)
                results.append(analysis)
            except Exception as error:
                errors.append((file, str(error)))
            progress.advance(task)

    if as_json:
        click.echo(json.dumps([r.to_dict(notation) for r in results], indent=2))
    else:
        table = Table(title=f"CueKey analysis ({len(results)} tracks)")
        table.add_column("Track", max_width=42)
        table.add_column("Key", justify="center")
        table.add_column("BPM", justify="right")
        table.add_column("Energy", justify="center")
        table.add_column("Cues", justify="center")
        for r in results:
            table.add_row(
                r.path.name,
                r.key.key.notation(notation),
                f"{r.bpm:.1f}",
                str(r.energy),
                str(len(r.cues)),
            )
        console.print(table)

    for file, message in errors:
        console.print(f"[red]error:[/red] {file.name}: {message}")
    if tags and results:
        console.print(f"[green]Tags written to {len(results)} files.[/green]")


@main.command()
@click.argument("collection_xml", type=click.Path(exists=True, path_type=Path))
@click.option("-o", "--output", type=click.Path(path_type=Path), required=True, help="Enriched XML output path.")
@click.option("--playlist", default=None, help="Only analyze tracks in this playlist.")
@click.option("--notation", type=click.Choice(NOTATIONS), default="camelot", show_default=True)
@click.option("--hot-cues", is_flag=True, help="Also write cues as hot cues A-H (default: memory cues only).")
@click.option(
    "--replace-cues", is_flag=True,
    help="Regenerate all cues, discarding existing ones (default: existing cues are preserved).",
)
@click.option("--tags", is_flag=True, help="Also write results into the audio file tags.")
@click.option("--limit", type=int, default=None, help="Stop after N tracks (for a quick trial run).")
def rekordbox(
    collection_xml: Path,
    output: Path,
    playlist: str | None,
    notation: str,
    hot_cues: bool,
    replace_cues: bool,
    tags: bool,
    limit: int | None,
) -> None:
    """Enrich a rekordbox XML collection with key, BPM, energy and cues.

    Export your collection from rekordbox (File > Export Collection in xml
    format), run this command, then import the output XML back in rekordbox
    (Preferences > Advanced > Database > rekordbox xml).
    """
    from cuekey.analyzer import analyze_file
    from cuekey.rekordbox import RekordboxCollection, enrich_collection
    from cuekey.tagging import write_tags

    total = len(RekordboxCollection.load(collection_xml).tracks_in_playlist(playlist))
    if limit is not None:
        total = min(total, limit)

    with _progress() as progress:
        task = progress.add_task("Analyzing collection", total=total)

        def on_track(track, analysis, error) -> None:
            if error is not None:
                console.print(f"[red]error:[/red] {track.name}: {error}")
                return
            if tags and analysis is not None:
                try:
                    write_tags(analysis.path, analysis, notation=notation)
                except Exception as tag_error:
                    console.print(f"[red]tag error:[/red] {track.name}: {tag_error}")
            progress.update(task, description=f"Analyzed {track.name[:40]}")
            progress.advance(task)

        count = enrich_collection(
            collection_xml,
            output,
            analyze=analyze_file,
            playlist=playlist,
            notation=notation,
            hot_cues=hot_cues,
            replace_cues=replace_cues,
            limit=limit,
            on_track=on_track,
        )

    console.print(f"[green]{count} tracks analyzed → {output}[/green]")
    console.print("Import it in rekordbox: Preferences → Advanced → Database → rekordbox xml")


if __name__ == "__main__":
    main()
