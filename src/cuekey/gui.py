"""CueKey desktop app (Tkinter).

A thin GUI over the same analysis pipeline as the CLI: add audio files or
a folder (or pick a rekordbox XML collection), watch progress, and get
key / BPM / energy / cues per track. Analysis runs on a worker thread;
the UI thread only consumes events from a queue.
"""

from __future__ import annotations

import os
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from cuekey import __version__
from cuekey.audio import is_supported

NOTATIONS = ("camelot", "openkey", "standard")

AUDIO_FILETYPES = [
    ("Audio files", "*.mp3 *.m4a *.aac *.flac *.wav *.aiff *.aif *.ogg *.opus"),
    ("All files", "*.*"),
]


class CueKeyApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.files: list[Path] = []
        self.events: queue.Queue = queue.Queue()
        self.worker: threading.Thread | None = None

        root.title(f"CueKey {__version__}")
        root.geometry("760x560")
        root.minsize(640, 480)

        self._build_ui()
        root.after(100, self._poll_events)

    # ------------------------------------------------------------------ UI

    def _build_ui(self) -> None:
        main = ttk.Frame(self.root, padding=12)
        main.pack(fill="both", expand=True)

        header = ttk.Label(main, text="CueKey", font=("Helvetica", 20, "bold"))
        header.pack(anchor="w")
        ttk.Label(
            main,
            text="Key, BPM, energy and cue points for harmonic mixing",
        ).pack(anchor="w", pady=(0, 10))

        toolbar = ttk.Frame(main)
        toolbar.pack(fill="x", pady=(0, 8))
        ttk.Button(toolbar, text="Add Files…", command=self._add_files).pack(side="left")
        ttk.Button(toolbar, text="Add Folder…", command=self._add_folder).pack(side="left", padx=(6, 0))
        ttk.Button(toolbar, text="Clear", command=self._clear).pack(side="left", padx=(6, 0))
        ttk.Button(toolbar, text="rekordbox XML…", command=self._enrich_rekordbox).pack(side="right")

        options = ttk.Frame(main)
        options.pack(fill="x", pady=(0, 8))
        ttk.Label(options, text="Notation:").pack(side="left")
        self.notation = tk.StringVar(value="camelot")
        ttk.Combobox(
            options, textvariable=self.notation, values=NOTATIONS, state="readonly", width=10
        ).pack(side="left", padx=(4, 16))
        self.write_tags = tk.BooleanVar(value=False)
        ttk.Checkbutton(options, text="Write file tags", variable=self.write_tags).pack(side="left")
        self.hot_cues = tk.BooleanVar(value=False)
        ttk.Checkbutton(options, text="Hot cues (XML)", variable=self.hot_cues).pack(side="left", padx=(16, 0))

        columns = ("track", "key", "bpm", "energy", "cues")
        self.table = ttk.Treeview(main, columns=columns, show="headings", height=14)
        for column, title, width, anchor in (
            ("track", "Track", 340, "w"),
            ("key", "Key", 70, "center"),
            ("bpm", "BPM", 80, "e"),
            ("energy", "Energy", 70, "center"),
            ("cues", "Cues", 60, "center"),
        ):
            self.table.heading(column, text=title)
            self.table.column(column, width=width, anchor=anchor)
        scrollbar = ttk.Scrollbar(main, orient="vertical", command=self.table.yview)
        self.table.configure(yscrollcommand=scrollbar.set)
        self.table.pack(side="top", fill="both", expand=True)
        scrollbar.place(relx=1.0, rely=0.5, anchor="e", relheight=0.5)

        bottom = ttk.Frame(main)
        bottom.pack(fill="x", pady=(10, 0))
        self.analyze_button = ttk.Button(bottom, text="Analyze", command=self._analyze)
        self.analyze_button.pack(side="right")
        self.progress = ttk.Progressbar(bottom, mode="determinate")
        self.progress.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.status = ttk.Label(main, text="Add audio files or pick a rekordbox XML to start.")
        self.status.pack(anchor="w", pady=(6, 0))

    # ------------------------------------------------------------- actions

    def _add_files(self) -> None:
        picked = filedialog.askopenfilenames(title="Choose audio files", filetypes=AUDIO_FILETYPES)
        self._extend_files(Path(p) for p in picked)

    def _add_folder(self) -> None:
        folder = filedialog.askdirectory(title="Choose a music folder")
        if folder:
            self._extend_files(p for p in sorted(Path(folder).rglob("*")) if p.is_file())

    def _extend_files(self, candidates) -> None:
        known = set(self.files)
        added = 0
        for path in candidates:
            if is_supported(path) and path not in known:
                self.files.append(path)
                known.add(path)
                self.table.insert("", "end", values=(path.name, "", "", "", ""))
                added += 1
        self._set_status(f"{len(self.files)} tracks queued (+{added}).")

    def _clear(self) -> None:
        self.files.clear()
        self.table.delete(*self.table.get_children())
        self.progress["value"] = 0
        self._set_status("Cleared.")

    def _set_status(self, text: str) -> None:
        self.status.configure(text=text)

    def _busy(self, busy: bool) -> None:
        self.analyze_button.configure(state="disabled" if busy else "normal")

    # ------------------------------------------------------- analyze files

    def _analyze(self) -> None:
        if self.worker and self.worker.is_alive():
            return
        if not self.files:
            messagebox.showinfo("CueKey", "Add some audio files first.")
            return
        self._busy(True)
        self.progress.configure(maximum=len(self.files), value=0)
        files = list(self.files)
        notation = self.notation.get()
        tags = self.write_tags.get()
        self.worker = threading.Thread(
            target=self._analyze_worker, args=(files, notation, tags), daemon=True
        )
        self.worker.start()

    def _analyze_worker(self, files: list[Path], notation: str, tags: bool) -> None:
        from cuekey.analyzer import analyze_file
        from cuekey.tagging import write_tags

        for index, path in enumerate(files):
            try:
                analysis = analyze_file(path)
                if tags:
                    write_tags(path, analysis, notation=notation)
                self.events.put(("row", index, analysis, notation))
            except Exception as error:
                self.events.put(("row_error", index, path, str(error)))
        self.events.put(("done", f"Analyzed {len(files)} tracks."))

    # --------------------------------------------------------- rekordbox

    def _enrich_rekordbox(self) -> None:
        if self.worker and self.worker.is_alive():
            return
        xml_in = filedialog.askopenfilename(
            title="Choose the rekordbox XML collection", filetypes=[("rekordbox XML", "*.xml")]
        )
        if not xml_in:
            return
        xml_in_path = Path(xml_in)
        xml_out = filedialog.asksaveasfilename(
            title="Save enriched XML as",
            defaultextension=".xml",
            initialfile=f"{xml_in_path.stem}-cuekey.xml",
        )
        if not xml_out:
            return
        self._busy(True)
        self._set_status("Reading collection…")
        self.worker = threading.Thread(
            target=self._rekordbox_worker,
            args=(xml_in_path, Path(xml_out), self.notation.get(), self.hot_cues.get(), self.write_tags.get()),
            daemon=True,
        )
        self.worker.start()

    def _rekordbox_worker(
        self, xml_in: Path, xml_out: Path, notation: str, hot_cues: bool, tags: bool
    ) -> None:
        from cuekey.analyzer import analyze_file
        from cuekey.rekordbox import RekordboxCollection, enrich_collection
        from cuekey.tagging import write_tags

        try:
            total = len(RekordboxCollection.load(xml_in).tracks_in_playlist(None))
            self.events.put(("total", total))

            def on_track(track, analysis, error) -> None:
                if error is not None:
                    self.events.put(("xml_error", track.name, str(error)))
                    return
                if tags and analysis is not None:
                    try:
                        write_tags(analysis.path, analysis, notation=notation)
                    except Exception:
                        pass  # tag failures must not stop the batch
                self.events.put(("xml_row", track.name, analysis, notation))

            count = enrich_collection(
                xml_in, xml_out, analyze=analyze_file,
                notation=notation, hot_cues=hot_cues, on_track=on_track,
            )
            self.events.put(("done", f"{count} tracks analyzed → {xml_out.name}. "
                                     "Import it via rekordbox Preferences → Advanced → Database."))
        except Exception as error:
            self.events.put(("fatal", str(error)))

    # ------------------------------------------------------------- events

    def _poll_events(self) -> None:
        try:
            while True:
                event = self.events.get_nowait()
                self._handle_event(event)
        except queue.Empty:
            pass
        self.root.after(100, self._poll_events)

    def _handle_event(self, event: tuple) -> None:
        kind = event[0]
        if kind == "row":
            _, index, analysis, notation = event
            item = self.table.get_children()[index]
            self.table.item(item, values=(
                analysis.path.name,
                analysis.key.key.notation(notation),
                f"{analysis.bpm:.1f}",
                analysis.energy,
                len(analysis.cues),
            ))
            self.progress.step(1)
        elif kind == "row_error":
            _, index, path, message = event
            item = self.table.get_children()[index]
            self.table.item(item, values=(path.name, "error", "", "", ""))
            self.progress.step(1)
            self._set_status(f"Error in {path.name}: {message}")
        elif kind == "total":
            self.progress.configure(maximum=max(event[1], 1), value=0)
            self._set_status(f"Analyzing {event[1]} tracks from collection…")
        elif kind == "xml_row":
            _, name, analysis, notation = event
            self.table.insert("", "end", values=(
                name,
                analysis.key.key.notation(notation),
                f"{analysis.bpm:.1f}",
                analysis.energy,
                len(analysis.cues),
            ))
            self.progress.step(1)
        elif kind == "xml_error":
            _, name, message = event
            self.table.insert("", "end", values=(name, "error", "", "", ""))
            self.progress.step(1)
        elif kind == "done":
            self._busy(False)
            self._set_status(event[1])
        elif kind == "fatal":
            self._busy(False)
            self._set_status(f"Failed: {event[1]}")
            messagebox.showerror("CueKey", event[1])


def main() -> None:
    root = tk.Tk()
    CueKeyApp(root)
    if os.environ.get("CUEKEY_SMOKE"):
        root.update()
        root.destroy()
        return
    root.mainloop()


if __name__ == "__main__":
    main()
