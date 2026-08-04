"""Full-track analysis pipeline: key + tempo + energy + cues.

analyze_file() runs a single track. analyze_many() is the batch front-end
used by the CLI, the GUI and the rekordbox flow: it reuses cached results
(see cuekey.cache) and fans misses out to a process pool sized to the CPU
(librosa is CPU-bound, so threads would serialize on the GIL).
"""

from __future__ import annotations

import multiprocessing
import os
from concurrent import futures
from pathlib import Path
from typing import Callable

from cuekey.analysis.cues import detect_cues
from cuekey.analysis.energy import detect_energy
from cuekey.analysis.key import detect_key
from cuekey.analysis.tempo import detect_tempo
from cuekey.audio import load_audio
from cuekey.models import TrackAnalysis

# on_result(path, analysis | None, error | None), called as results arrive.
OnResult = Callable[[Path, TrackAnalysis | None, Exception | None], None]


def analyze_file(path: Path, with_cues: bool = True) -> TrackAnalysis:
    y, sr = load_audio(path)
    duration = len(y) / sr

    grid = detect_tempo(y, sr)
    key = detect_key(y, sr)
    energy = detect_energy(y, sr, grid.bpm)
    cues = detect_cues(y, sr, grid) if with_cues else []

    return TrackAnalysis(
        path=path,
        duration=duration,
        bpm=grid.bpm,
        key=key,
        energy=energy,
        cues=cues,
    )


def default_workers() -> int:
    """Leave two cores for the UI and the OS."""
    return max(1, (os.cpu_count() or 2) - 2)


def _warm_worker() -> None:
    import librosa  # noqa: F401  # pay the heavy import once per worker


def _analyze_task(path_str: str, with_cues: bool) -> TrackAnalysis:
    return analyze_file(Path(path_str), with_cues=with_cues)


def analyze_many(
    paths: list[Path],
    on_result: OnResult,
    with_cues: bool = True,
    max_workers: int | None = None,
    use_cache: bool = True,
    should_stop: Callable[[], bool] | None = None,
) -> int:
    """Analyze a batch of files; returns the number of successful analyses.

    Cached results are delivered first (instantly); the rest run on a
    process pool. should_stop is polled between dispatches and may block
    (pause); once it returns True no new work starts and queued-but-not-
    started tasks are cancelled, while running ones finish.
    """
    from cuekey.cache import AnalysisCache

    cache = AnalysisCache() if use_cache else None
    succeeded = 0
    misses: list[Path] = []

    for path in paths:
        if should_stop is not None and should_stop():
            return succeeded
        cached = cache.get(path, require_cues=with_cues) if cache else None
        if cached is not None:
            succeeded += 1
            on_result(path, cached, None)
        else:
            misses.append(path)

    if not misses:
        return succeeded

    workers = max_workers if max_workers is not None else default_workers()
    workers = min(workers, len(misses))

    if workers <= 1:
        for path in misses:
            if should_stop is not None and should_stop():
                break
            try:
                analysis = analyze_file(path, with_cues=with_cues)
                if cache:
                    cache.put(path, analysis, has_cues=with_cues)
                succeeded += 1
                on_result(path, analysis, None)
            except Exception as error:  # one bad file must not kill the batch
                on_result(path, None, error)
        return succeeded

    context = multiprocessing.get_context("spawn")
    stopped = False
    with futures.ProcessPoolExecutor(
        max_workers=workers, mp_context=context, initializer=_warm_worker
    ) as pool:
        in_flight: dict[futures.Future, Path] = {}
        pending = iter(misses)

        def submit_next() -> bool:
            nonlocal stopped
            if stopped:
                return False
            if should_stop is not None and should_stop():
                stopped = True
                # Drop everything that has not started running yet.
                for future in list(in_flight):
                    if future.cancel():
                        del in_flight[future]
                return False
            path = next(pending, None)
            if path is None:
                return False
            in_flight[pool.submit(_analyze_task, str(path), with_cues)] = path
            return True

        for _ in range(workers + 2):  # small buffer keeps the pool fed
            if not submit_next():
                break

        while in_flight:
            done, _ = futures.wait(list(in_flight), return_when=futures.FIRST_COMPLETED)
            for future in done:
                path = in_flight.pop(future)
                try:
                    analysis = future.result()
                    if cache:
                        cache.put(path, analysis, has_cues=with_cues)
                    succeeded += 1
                    on_result(path, analysis, None)
                except futures.CancelledError:
                    pass
                except Exception as error:
                    on_result(path, None, error)
                submit_next()

    return succeeded
