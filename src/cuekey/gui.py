"""CueKey desktop app.

Dark, DJ-booth-friendly UI (CustomTkinter) over the same analysis engine
as the CLI. Rows are tinted by detected key so harmonically compatible
tracks share a color; a detail panel shows the selected track's key badge,
BPM and an energy meter. Analysis runs on a worker thread; the UI thread
only consumes events from a queue.
"""

from __future__ import annotations

import colorsys
import os
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import customtkinter as ctk

from cuekey import __version__
from cuekey.audio import is_supported
from cuekey.camelot import Key
from cuekey.models import TrackAnalysis

NOTATIONS = ("camelot", "openkey", "standard")

AUDIO_FILETYPES = [
    ("Audio files", "*.mp3 *.m4a *.aac *.flac *.wav *.aiff *.aif *.ogg *.opus"),
    ("All files", "*.*"),
]

BG = "#0e0f13"
PANEL = "#16171d"
PANEL_2 = "#1c1d25"
TABLE_BG = "#12131a"
TABLE_ROW_ALT = "#171821"
TEXT = "#e8e9ee"
TEXT_DIM = "#8a8d99"
ACCENT = "#7c5cff"
ACCENT_HOVER = "#6847e6"


def key_color(key: Key) -> str:
    """One hue per wheel position, so compatible keys share a color family."""
    hue = (key.wheel_number - 1) / 12.0
    saturation = 0.62 if key.mode == "minor" else 0.80
    r, g, b = colorsys.hsv_to_rgb(hue, saturation, 0.95)
    return f"#{int(r * 255):02x}{int(g * 255):02x}{int(b * 255):02x}"


def energy_color(energy: int) -> str:
    """Cool teal (1) → amber → hot red (10)."""
    hue = 0.45 * (1 - (energy - 1) / 9.0)
    r, g, b = colorsys.hsv_to_rgb(hue, 0.85, 0.95)
    return f"#{int(r * 255):02x}{int(g * 255):02x}{int(b * 255):02x}"


def mmss(seconds: float) -> str:
    return f"{int(seconds) // 60:02d}:{int(seconds) % 60:02d}"


class CueKeyApp:
    def __init__(self, root: ctk.CTk):
        self.root = root
        self.files: list[Path] = []
        self.results: dict[str, TrackAnalysis] = {}  # table item id -> analysis
        self.events: queue.Queue = queue.Queue()
        self.worker: threading.Thread | None = None

        root.title("CueKey")
        root.geometry("900x640")
        root.minsize(760, 540)
        root.configure(fg_color=BG)

        self._build_ui()
        root.after(100, self._poll_events)

    # ------------------------------------------------------------------ UI

    def _build_ui(self) -> None:
        main = ctk.CTkFrame(self.root, fg_color=BG)
        main.pack(fill="both", expand=True, padx=16, pady=14)

        self._build_header(main)
        self._build_toolbar(main)
        self._build_table(main)
        self._build_detail_panel(main)
        self._build_footer(main)

    def _build_header(self, parent) -> None:
        header = ctk.CTkFrame(parent, fg_color=BG)
        header.pack(fill="x")
        title = ctk.CTkLabel(
            header, text="◈ CueKey", text_color=ACCENT,
            font=ctk.CTkFont(size=26, weight="bold"),
        )
        title.pack(side="left")
        ctk.CTkLabel(
            header, text="  key · BPM · energy · cues", text_color=TEXT_DIM,
            font=ctk.CTkFont(size=14),
        ).pack(side="left", pady=(6, 0))
        ctk.CTkLabel(
            header, text=f"v{__version__}", text_color=TEXT_DIM,
            font=ctk.CTkFont(size=12),
        ).pack(side="right", pady=(6, 0))

    def _build_toolbar(self, parent) -> None:
        bar = ctk.CTkFrame(parent, fg_color=PANEL, corner_radius=12)
        bar.pack(fill="x", pady=(10, 8))
        inner = ctk.CTkFrame(bar, fg_color=PANEL)
        inner.pack(fill="x", padx=10, pady=8)

        def button(text, command, primary=False):
            return ctk.CTkButton(
                inner, text=text, command=command, corner_radius=8, height=30,
                width=108,
                fg_color=ACCENT if primary else PANEL_2,
                hover_color=ACCENT_HOVER if primary else "#262833",
                text_color=TEXT,
            )

        button("+ Files", self._add_files).pack(side="left")
        button("+ Folder", self._add_folder).pack(side="left", padx=(6, 0))
        button("Clear", self._clear).pack(side="left", padx=(6, 0))
        button("rekordbox XML…", self._enrich_rekordbox).pack(side="right")

        self.notation = tk.StringVar(value="camelot")
        ctk.CTkOptionMenu(
            inner, variable=self.notation, values=list(NOTATIONS), width=110, height=30,
            fg_color=PANEL_2, button_color=PANEL_2, button_hover_color="#262833",
            dropdown_fg_color=PANEL_2, text_color=TEXT, corner_radius=8,
        ).pack(side="left", padx=(18, 0))

        self.write_tags = tk.BooleanVar(value=False)
        ctk.CTkSwitch(
            inner, text="Write tags", variable=self.write_tags,
            progress_color=ACCENT, text_color=TEXT_DIM, switch_height=16, switch_width=36,
        ).pack(side="left", padx=(16, 0))
        self.hot_cues = tk.BooleanVar(value=False)
        ctk.CTkSwitch(
            inner, text="Hot cues (XML)", variable=self.hot_cues,
            progress_color=ACCENT, text_color=TEXT_DIM, switch_height=16, switch_width=36,
        ).pack(side="left", padx=(12, 0))

    def _build_table(self, parent) -> None:
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "CueKey.Treeview",
            background=TABLE_BG, fieldbackground=TABLE_BG, foreground=TEXT,
            rowheight=30, borderwidth=0, font=("Helvetica", 13),
        )
        style.configure(
            "CueKey.Treeview.Heading",
            background=PANEL, foreground=TEXT_DIM, borderwidth=0,
            font=("Helvetica", 12, "bold"),
        )
        style.map("CueKey.Treeview", background=[("selected", "#2a2c3a")])

        holder = ctk.CTkFrame(parent, fg_color=TABLE_BG, corner_radius=12)
        holder.pack(fill="both", expand=True)

        columns = ("track", "key", "bpm", "energy", "cues")
        self.table = ttk.Treeview(
            holder, columns=columns, show="headings", style="CueKey.Treeview"
        )
        for column, heading, width, anchor in (
            ("track", "TRACK", 380, "w"),
            ("key", "KEY", 70, "center"),
            ("bpm", "BPM", 80, "e"),
            ("energy", "ENERGY", 110, "center"),
            ("cues", "CUES", 60, "center"),
        ):
            self.table.heading(column, text=heading)
            self.table.column(column, width=width, anchor=anchor)

        scrollbar = ctk.CTkScrollbar(holder, command=self.table.yview, fg_color=TABLE_BG)
        self.table.configure(yscrollcommand=scrollbar.set)
        self.table.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=8)
        scrollbar.pack(side="right", fill="y", pady=8)

        self.table.tag_configure("alt", background=TABLE_ROW_ALT)
        self.table.bind("<<TreeviewSelect>>", self._on_select)

    def _build_detail_panel(self, parent) -> None:
        panel = ctk.CTkFrame(parent, fg_color=PANEL, corner_radius=12, height=86)
        panel.pack(fill="x", pady=(8, 0))
        panel.pack_propagate(False)

        self.key_badge = ctk.CTkLabel(
            panel, text="—", width=96, corner_radius=10,
            fg_color=PANEL_2, text_color=TEXT,
            font=ctk.CTkFont(size=24, weight="bold"),
        )
        self.key_badge.pack(side="left", padx=(14, 12), pady=14, fill="y")

        info = ctk.CTkFrame(panel, fg_color=PANEL)
        info.pack(side="left", fill="both", expand=True, pady=10)
        self.detail_title = ctk.CTkLabel(
            info, text="Select a track", text_color=TEXT, anchor="w",
            font=ctk.CTkFont(size=15, weight="bold"),
        )
        self.detail_title.pack(fill="x")
        self.detail_sub = ctk.CTkLabel(
            info, text="Key, BPM, energy and cue points will show here.",
            text_color=TEXT_DIM, anchor="w", font=ctk.CTkFont(size=12),
        )
        self.detail_sub.pack(fill="x")

        meter = ctk.CTkFrame(panel, fg_color=PANEL)
        meter.pack(side="right", padx=14, pady=14)
        self.energy_label = ctk.CTkLabel(
            meter, text="ENERGY —", text_color=TEXT_DIM,
            font=ctk.CTkFont(size=11, weight="bold"),
        )
        self.energy_label.pack(anchor="e")
        self.energy_bar = ctk.CTkProgressBar(
            meter, width=180, height=10, corner_radius=5,
            fg_color=PANEL_2, progress_color=ACCENT,
        )
        self.energy_bar.set(0)
        self.energy_bar.pack(pady=(6, 0))

    def _build_footer(self, parent) -> None:
        footer = ctk.CTkFrame(parent, fg_color=BG)
        footer.pack(fill="x", pady=(10, 0))
        self.analyze_button = ctk.CTkButton(
            footer, text="▶ Analyze", command=self._analyze, corner_radius=8,
            height=34, width=130, fg_color=ACCENT, hover_color=ACCENT_HOVER,
            font=ctk.CTkFont(size=14, weight="bold"),
        )
        self.analyze_button.pack(side="right")
        self.progress = ctk.CTkProgressBar(
            footer, height=10, corner_radius=5, fg_color=PANEL_2, progress_color=ACCENT
        )
        self.progress.set(0)
        self.progress.pack(side="left", fill="x", expand=True, padx=(0, 14), pady=12)
        self._progress_total = 0
        self._progress_done = 0

        self.status = ctk.CTkLabel(
            parent, text="Add audio files or pick a rekordbox XML to start.",
            text_color=TEXT_DIM, anchor="w", font=ctk.CTkFont(size=12),
        )
        self.status.pack(fill="x", pady=(6, 0))

    # ------------------------------------------------------------- helpers

    def _set_status(self, text: str) -> None:
        self.status.configure(text=text)

    def _busy(self, busy: bool) -> None:
        self.analyze_button.configure(state="disabled" if busy else "normal")

    def _progress_reset(self, total: int) -> None:
        self._progress_total = max(total, 1)
        self._progress_done = 0
        self.progress.set(0)

    def _progress_step(self) -> None:
        self._progress_done += 1
        self.progress.set(self._progress_done / self._progress_total)

    def _row_values(self, name: str, analysis: TrackAnalysis, notation: str) -> tuple:
        blocks = "▮" * analysis.energy + "▯" * (10 - analysis.energy)
        return (
            f"  {name}",
            analysis.key.key.notation(notation),
            f"{analysis.bpm:.1f}",
            blocks,
            len(analysis.cues),
        )

    def _row_tags(self, item: str, analysis: TrackAnalysis) -> tuple:
        code = analysis.key.key.camelot
        tag = f"key-{code}"
        self.table.tag_configure(tag, foreground=key_color(analysis.key.key))
        alt = ("alt",) if self.table.index(item) % 2 else ()
        return (tag, *alt)

    def _set_row(self, item: str, name: str, analysis: TrackAnalysis, notation: str) -> None:
        self.table.item(item, values=self._row_values(name, analysis, notation),
                        tags=self._row_tags(item, analysis))
        self.results[item] = analysis

    def _on_select(self, _event=None) -> None:
        selection = self.table.selection()
        if not selection or selection[0] not in self.results:
            return
        analysis = self.results[selection[0]]
        key = analysis.key.key
        notation = self.notation.get()
        self.key_badge.configure(
            text=key.notation(notation), fg_color=key_color(key), text_color="#0b0c10"
        )
        self.detail_title.configure(text=analysis.path.name)
        cues = " · ".join(mmss(c.seconds) for c in analysis.cues) or "none"
        self.detail_sub.configure(
            text=f"{key.standard}  ·  {analysis.bpm:.1f} BPM  ·  {mmss(analysis.duration)}  ·  cues: {cues}"
        )
        self.energy_label.configure(
            text=f"ENERGY {analysis.energy}", text_color=energy_color(analysis.energy)
        )
        self.energy_bar.configure(progress_color=energy_color(analysis.energy))
        self.energy_bar.set(analysis.energy / 10)

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
                tags = ("alt",) if len(self.table.get_children()) % 2 else ()
                self.table.insert("", "end", values=(f"  {path.name}", "", "", "", ""), tags=tags)
                added += 1
        self._set_status(f"{len(self.files)} tracks queued (+{added}).")

    def _clear(self) -> None:
        self.files.clear()
        self.results.clear()
        self.table.delete(*self.table.get_children())
        self.progress.set(0)
        self._set_status("Cleared.")

    # ------------------------------------------------------- analyze files

    def _analyze(self) -> None:
        if self.worker and self.worker.is_alive():
            return
        if not self.files:
            messagebox.showinfo("CueKey", "Add some audio files first.")
            return
        self._busy(True)
        self._progress_reset(len(self.files))
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
            self._set_row(item, analysis.path.name, analysis, notation)
            self._progress_step()
        elif kind == "row_error":
            _, index, path, message = event
            item = self.table.get_children()[index]
            self.table.item(item, values=(f"  {path.name}", "✕", "", "", ""))
            self._progress_step()
            self._set_status(f"Error in {path.name}: {message}")
        elif kind == "total":
            self._progress_reset(event[1])
            self._set_status(f"Analyzing {event[1]} tracks from collection…")
        elif kind == "xml_row":
            _, name, analysis, notation = event
            item = self.table.insert("", "end")
            self._set_row(item, name, analysis, notation)
            self._progress_step()
        elif kind == "xml_error":
            _, name, message = event
            self.table.insert("", "end", values=(f"  {name}", "✕", "", "", ""))
            self._progress_step()
        elif kind == "done":
            self._busy(False)
            self._set_status(event[1])
        elif kind == "fatal":
            self._busy(False)
            self._set_status(f"Failed: {event[1]}")
            messagebox.showerror("CueKey", event[1])


def main() -> None:
    ctk.set_appearance_mode("dark")
    root = ctk.CTk()
    CueKeyApp(root)
    if os.environ.get("CUEKEY_SMOKE"):
        root.update()
        root.destroy()
        return
    root.mainloop()


if __name__ == "__main__":
    main()
