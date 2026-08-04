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
    """Leave two cores for the UI/OS and cap by RAM (analysis peaks at
    roughly 2 GB per worker on long tracks)."""
    by_cores = max(1, (os.cpu_count() or 2) - 2)
    try:
        ram_gb = os.sysconf("SC_PHYS_PAGES") * os.sysconf("SC_PAGE_SIZE") / 2**30
        by_ram = max(1, int(ram_gb / 2.5))
    except (ValueError, OSError, AttributeError):
        by_ram = by_cores
    return min(by_cores, by_ram)


def enable_crash_diagnostics() -> None:
    """Dump the Python traceback to a log on hard crashes (SIGSEGV etc.).

    PyInstaller apps ignore PYTHONFAULTHANDLER, so enable it in code; the
    log names the exact librosa/numpy call that took the process down.
    """
    import faulthandler

    try:
        log_dir = Path.home() / "Library" / "Logs" / "CueKey"
        log_dir.mkdir(parents=True, exist_ok=True)
        handle = open(log_dir / f"crash-{os.getpid()}.log", "w")  # noqa: SIM115 (must outlive scope)
        faulthandler.enable(file=handle)
    except OSError:
        pass


def _isolate_numba_cache() -> None:
    """Point numba's JIT cache at a private temp dir for this process.

    librosa compiles its numba functions with cache=True; with a shared
    cache directory (inside the app bundle, no less) concurrent workers
    race on the cache files and corrupted entries produce NULL loop
    pointers — a segfault at call time.
    """
    import tempfile

    os.environ["NUMBA_CACHE_DIR"] = tempfile.mkdtemp(prefix="cuekey-numba-")


def _warm_worker() -> None:
    enable_crash_diagnostics()
    _isolate_numba_cache()
    import librosa  # noqa: F401  # pay the heavy import once per worker


def _log_worker_crash(path: Path) -> None:
    """Record files that killed a worker so root causes can be chased later."""
    try:
        log_dir = Path.home() / "Library" / "Logs" / "CueKey"
        log_dir.mkdir(parents=True, exist_ok=True)
        with open(log_dir / "worker-crashes.log", "a", encoding="utf-8") as log:
            log.write(f"{path}\n")
    except OSError:
        pass


def _analyze_task(path_str: str, with_cues: bool) -> TrackAnalysis:
    if os.environ.get("CUEKEY_TEST_CRASH") and Path(path_str).name.startswith("crashme"):
        os._exit(1)  # test hook: simulate a native decoder crash
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

    from collections import deque
    from concurrent.futures.process import BrokenProcessPool

    context = multiprocessing.get_context("spawn")
    stopped = False
    queue: deque[Path] = deque(misses)
    quarantine: deque[Path] = deque()  # crash suspects, retried one at a time
    rebuilds = 0
    max_rebuilds = 10 + len(misses) // 25

    while (queue or quarantine) and not stopped and rebuilds <= max_rebuilds:
        pool = futures.ProcessPoolExecutor(
            max_workers=workers, mp_context=context, initializer=_warm_worker,
            max_tasks_per_child=16,  # recycle workers so memory can't creep
        )
        in_flight: dict[futures.Future, Path] = {}

        def submit_next() -> bool:
            nonlocal stopped
            if stopped:
                return False
            if should_stop is not None and should_stop():
                stopped = True
                for future in list(in_flight):  # drop not-yet-started work
                    if future.cancel():
                        del in_flight[future]
                return False
            if quarantine:
                # Isolate suspects: exactly one in flight, so a crash
                # unambiguously identifies the culprit file.
                if in_flight:
                    return False
                path = quarantine.popleft()
            elif queue:
                path = queue.popleft()
            else:
                return False
            in_flight[pool.submit(_analyze_task, str(path), with_cues)] = path
            return True

        try:
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
                    except BrokenProcessPool:
                        in_flight[future] = path  # count it among the crashed
                        raise  # handled by the outer except: rebuild the pool
                    except Exception as error:
                        on_result(path, None, error)
                    submit_next()
            pool.shutdown()
            break  # batch finished (or stopped) without a crash
        except BrokenProcessPool:
            # A worker died (native crash / killed). Report or retry the
            # tracks that were in flight, then continue with a fresh pool.
            rebuilds += 1
            crashed = list(in_flight.values())
            if len(crashed) == 1:
                _log_worker_crash(crashed[0])
                on_result(crashed[0], None, RuntimeError(
                    "analysis worker crashed on this file — logged to "
                    "~/Library/Logs/CueKey/worker-crashes.log"
                ))
            else:
                quarantine.extend(crashed)
            pool.shutdown(wait=False, cancel_futures=True)

    if rebuilds > max_rebuilds:
        for path in list(quarantine) + list(queue):
            on_result(path, None, RuntimeError(
                "skipped: analysis workers kept crashing"
            ))

    return succeeded
