/* CueKey frontend. Talks to the Python backend via window.pywebview.api;
   the backend pushes analysis events by calling CueKey.onEvent(...). */

"use strict";

const state = {
  tracks: [],          // {id, name, path, standard, camelot, openkey, wheel, mode, bpm, energy, cues[], duration, error}
  byId: new Map(),     // id -> track object (same objects as in tracks)
  selectedId: null,
  notation: "camelot",
  filter: "",
  sortKey: null,
  sortDir: 1,
  cueMode: "keep",
  total: 0,
  done: 0,
  busy: false,
  paused: false,
};

const $ = (id) => document.getElementById(id);

/* ------------------------------------------------------------- colors */

function keyColor(wheel, mode) {
  const hue = ((wheel - 1) / 12) * 360;
  const sat = mode === "minor" ? 52 : 72;
  return `hsl(${hue} ${sat}% 62%)`;
}

function energyColor(energy) {
  const hue = 162 * (1 - (energy - 1) / 9);   // teal → red
  return `hsl(${hue} 80% 55%)`;
}

function notationOf(track) {
  return track[state.notation === "standard" ? "standard" : state.notation];
}

const mmss = (s) => `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(Math.floor(s % 60)).padStart(2, "0")}`;

const fmtBpm = (b) => (Number.isInteger(b) ? String(b) : b.toFixed(1));

/* ------------------------------------------------------------- table */

function visibleTracks() {
  let rows = state.tracks;
  if (state.filter) {
    const q = state.filter.toLowerCase();
    rows = rows.filter((t) => t.name.toLowerCase().includes(q));
  }
  if (state.sortKey) {
    const k = state.sortKey, dir = state.sortDir;
    rows = [...rows].sort((a, b) => {
      const av = a[k], bv = b[k];
      if (av == null && bv == null) return 0;
      if (av == null) return 1;
      if (bv == null) return -1;
      return (typeof av === "string" ? av.localeCompare(bv) : av - bv) * dir;
    });
  }
  return rows;
}

const rowsById = new Map(); // id -> <tr> element currently in the DOM

function buildRow(t) {
  const tr = document.createElement("tr");
  tr.dataset.id = t.id;
  if (t.id === state.selectedId) tr.classList.add("selected");

  const name = document.createElement("td");
  name.className = "name";
  name.textContent = t.name;
  tr.appendChild(name);

  const key = document.createElement("td");
  key.className = "center";
  if (t.error) {
    key.innerHTML = `<span class="key-pill err">✕</span>`;
  } else if (t.wheel != null) {
    const pill = document.createElement("span");
    pill.className = "key-pill";
    pill.style.background = keyColor(t.wheel, t.mode);
    pill.textContent = notationOf(t);
    key.appendChild(pill);
  }
  tr.appendChild(key);

  const bpm = document.createElement("td");
  bpm.className = "right";
  bpm.textContent = t.bpm != null ? fmtBpm(t.bpm) : "";
  tr.appendChild(bpm);

  const energy = document.createElement("td");
  if (t.energy != null) {
    energy.innerHTML =
      `<div class="energy-cell"><div class="energy-bar"><div style="width:${t.energy * 10}%;` +
      `background:${energyColor(t.energy)}"></div></div><span class="n">${t.energy}</span></div>`;
  }
  tr.appendChild(energy);

  const cues = document.createElement("td");
  cues.className = "cues";
  cues.textContent = t.cues ? t.cues.length : "";
  tr.appendChild(cues);

  tr.addEventListener("click", () => selectTrack(t.id));
  return tr;
}

function renderTable() {
  const tbody = $("rows");
  const rows = visibleTracks();
  $("empty-state").style.display = state.tracks.length ? "none" : "flex";

  rowsById.clear();
  const fragment = document.createDocumentFragment();
  for (const t of rows) {
    const tr = buildRow(t);
    fragment.appendChild(tr);
    rowsById.set(t.id, tr);
  }
  tbody.replaceChildren(fragment);
}

function patchRow(t) {
  // Update one row in place — a full renderTable() per event is quadratic
  // on large collections.
  const existing = rowsById.get(t.id);
  if (state.filter && !t.name.toLowerCase().includes(state.filter.toLowerCase())) {
    if (existing) {
      existing.remove();
      rowsById.delete(t.id);
    }
    return;
  }
  const fresh = buildRow(t);
  if (existing) existing.replaceWith(fresh);
  else $("rows").appendChild(fresh);
  rowsById.set(t.id, fresh);
  $("empty-state").style.display = "none";
}

/* ------------------------------------------------------- detail + wheel */

const WHEEL_OUTER = 100, WHEEL_INNER_R = 62, WHEEL_MID = 82, WHEEL_HUB = 40;

function segmentPath(index, r0, r1) {
  const a0 = ((index - 0.5) / 12) * 2 * Math.PI - Math.PI / 2;
  const a1 = ((index + 0.5) / 12) * 2 * Math.PI - Math.PI / 2;
  const p = (r, a) => `${(r * Math.cos(a)).toFixed(2)},${(r * Math.sin(a)).toFixed(2)}`;
  return `M ${p(r0, a0)} A ${r0} ${r0} 0 0 1 ${p(r0, a1)} L ${p(r1, a1)} A ${r1} ${r1} 0 0 0 ${p(r1, a0)} Z`;
}

function buildWheel() {
  const svg = $("wheel");
  let markup = "";
  for (let n = 1; n <= 12; n++) {
    const i = n - 1;
    const angle = (i / 12) * 2 * Math.PI - Math.PI / 2;
    // Outer ring: major ("B" / "d"); inner ring: minor ("A" / "m").
    markup += `<path id="seg-${n}B" d="${segmentPath(i, WHEEL_OUTER, WHEEL_MID)}" fill="${keyColor(n, "major")}"/>`;
    markup += `<path id="seg-${n}A" d="${segmentPath(i, WHEEL_MID - 2, WHEEL_INNER_R)}" fill="${keyColor(n, "minor")}"/>`;
    const tx = (WHEEL_OUTER + WHEEL_MID) / 2 * Math.cos(angle);
    const ty = (WHEEL_OUTER + WHEEL_MID) / 2 * Math.sin(angle);
    markup += `<text x="${tx}" y="${ty}" text-anchor="middle" dominant-baseline="central">${n}</text>`;
  }
  markup += `<circle cx="0" cy="0" r="${WHEEL_HUB}" fill="#0b0c10"/>`;
  svg.innerHTML = markup;
  dimWheel(null);
}

function dimWheel(track) {
  const lit = new Set();
  if (track && track.wheel != null) {
    const n = track.wheel;
    const ring = track.mode === "minor" ? "A" : "B";
    const other = ring === "A" ? "B" : "A";
    const prev = ((n + 10) % 12) + 1, next = (n % 12) + 1;
    lit.add(`seg-${n}${ring}`);          // same key
    lit.add(`seg-${prev}${ring}`);       // -1 neighbour
    lit.add(`seg-${next}${ring}`);       // +1 neighbour
    lit.add(`seg-${n}${other}`);         // relative major/minor
  }
  for (const path of $("wheel").querySelectorAll("path")) {
    const on = lit.has(path.id);
    path.style.opacity = track ? (on ? 1 : 0.13) : 0.55;
    path.style.filter = on ? "drop-shadow(0 0 6px rgba(255,255,255,0.35))" : "none";
  }
}

function compatList(track) {
  const n = track.wheel;
  const ring = track.mode === "minor" ? "A" : "B";
  const other = ring === "A" ? "B" : "A";
  const prev = ((n + 10) % 12) + 1, next = (n % 12) + 1;
  return [`${n}${ring}`, `${prev}${ring}`, `${next}${ring}`, `${n}${other}`];
}

function selectTrack(id) {
  const previous = rowsById.get(state.selectedId);
  if (previous) previous.classList.remove("selected");
  state.selectedId = id;
  const current = rowsById.get(id);
  if (current) current.classList.add("selected");
  const track = state.byId.get(id);
  if (!track || track.wheel == null) return;

  const color = keyColor(track.wheel, track.mode);
  $("wheel-center").textContent = notationOf(track);
  $("wheel-center").style.color = color;
  dimWheel(track);

  $("detail-title").textContent = track.name;
  $("detail-meta").textContent =
    `${track.standard} · ${fmtBpm(track.bpm)} BPM · ${mmss(track.duration)}`;

  const meter = $("energy-meter");
  meter.innerHTML = "";
  for (let i = 1; i <= 10; i++) {
    const seg = document.createElement("i");
    if (i <= track.energy) seg.style.background = energyColor(track.energy);
    meter.appendChild(seg);
  }
  $("energy-num").textContent = track.energy;
  $("energy-num").style.color = energyColor(track.energy);

  const strip = $("cue-strip");
  strip.innerHTML = "";
  for (const c of track.cues) {
    const tick = document.createElement("i");
    tick.style.left = `${(c / track.duration) * 100}%`;
    tick.title = mmss(c);
    strip.appendChild(tick);
  }

  const pills = compatList(track).map((code) => {
    const num = parseInt(code, 10);
    const mode = code.endsWith("A") ? "minor" : "major";
    return `<span class="key-pill" style="background:${keyColor(num, mode)}">${code}</span>`;
  });
  $("compat").innerHTML = `<span class="label">MIX WITH</span><br>${pills.join("")}`;
}

/* ------------------------------------------------------------- events */

function setProgress() {
  const pct = state.total ? Math.round((state.done / state.total) * 100) : 0;
  $("progress-fill").style.width = `${pct}%`;
  $("progress-text").textContent = state.total ? `${state.done} / ${state.total} · ${pct}%` : "";
}

function setStatus(text) { $("status").textContent = text; }

function setBusy(busy) {
  state.busy = busy;
  state.paused = false;
  $("analyze-btn").disabled = busy;
  $("pause-btn").classList.toggle("hidden", !busy);
  $("cancel-btn").classList.toggle("hidden", !busy);
  $("pause-btn").textContent = "⏸ Pause";
}

function upsertTrack(data) {
  let track = state.byId.get(data.id);
  if (track) {
    Object.assign(track, data);
  } else {
    track = data;
    state.tracks.push(track);
    state.byId.set(track.id, track);
  }
  patchRow(track);
  return track;
}

const CueKey = {
  onEvent(event) {
    switch (event.type) {
      case "queued":
        // Bulk preload: insert everything, then render the table once.
        for (const q of event.tracks) {
          if (!state.byId.has(q.id)) {
            state.tracks.push(q);
            state.byId.set(q.id, q);
          }
        }
        renderTable();
        setStatus(`${state.tracks.length} tracks queued.`);
        break;
      case "total":
        state.total = event.total; state.done = 0;
        setProgress();
        setStatus(event.message || `Analyzing ${event.total} tracks…`);
        break;
      case "row":
        state.done += 1; setProgress();
        upsertTrack(event.track);
        if (state.selectedId === null) selectTrack(event.track.id);
        break;
      case "row_error":
        state.done += 1; setProgress();
        upsertTrack({ id: event.id, name: event.name, error: true });
        setStatus(`Error in ${event.name}: ${event.message}`);
        break;
      case "done":
        setBusy(false);
        if (state.total) { state.done = state.total; setProgress(); }
        setStatus(event.message);
        break;
      case "fatal":
        setBusy(false);
        setStatus(`Failed: ${event.message}`);
        break;
      case "status":
        setStatus(event.message);
        break;
    }
  },

  async addFiles() {
    if (state.busy) return;
    await window.pywebview.api.pick_files();
  },

  async addFolder() {
    if (state.busy) return;
    await window.pywebview.api.pick_folder();
  },

  async analyze() {
    if (state.busy) return;
    const pending = state.tracks.filter((t) => t.bpm == null && !t.error);
    if (!pending.length) { setStatus("Nothing to analyze — add audio files first."); return; }
    setBusy(true);
    state.total = pending.length; state.done = 0; setProgress();
    await window.pywebview.api.analyze(pending.map((t) => t.id), {
      notation: state.notation,
      write_tags: $("opt-tags").checked,
    });
  },

  async pauseResume() {
    if (!state.busy) return;
    state.paused = !state.paused;
    $("pause-btn").textContent = state.paused ? "▶ Resume" : "⏸ Pause";
    if (state.paused) await window.pywebview.api.pause_analysis();
    else await window.pywebview.api.resume_analysis();
  },

  async cancel() {
    if (!state.busy) return;
    await window.pywebview.api.cancel_analysis();
    setStatus("Cancelling — finishing the current track…");
  },

  openHelp() {
    $("help-modal").classList.add("open");
  },

  async donate() {
    await window.pywebview.api.open_donation();
  },

  closeHelp() {
    $("help-modal").classList.remove("open");
  },

  async enrichRekordbox() {
    if (state.busy) return;
    const started = await window.pywebview.api.enrich_rekordbox({
      notation: state.notation,
      write_tags: $("opt-tags").checked,
      hot_cues: $("opt-hotcues").checked,
      replace_cues: state.cueMode === "replace",
    });
    if (started) setBusy(true);
  },
};

window.CueKey = CueKey;

/* ------------------------------------------------------------ wiring */

function setHelpLanguage(lang, remember = false) {
  $("help-body").innerHTML = HELP_CONTENT[lang] || HELP_CONTENT.en;
  for (const b of $("help-lang").children) b.classList.toggle("active", b.dataset.value === lang);
  if (remember) {
    try { localStorage.setItem("cuekeyHelpLang", lang); } catch (e) { /* file:// may block storage */ }
  }
}

function storedHelpLanguage() {
  try { return localStorage.getItem("cuekeyHelpLang"); } catch (e) { return null; }
}

document.addEventListener("DOMContentLoaded", () => {
  buildWheel();
  renderTable();

  setHelpLanguage(storedHelpLanguage() || "en");
  $("help-lang").addEventListener("click", (e) => {
    const btn = e.target.closest("button");
    if (btn) setHelpLanguage(btn.dataset.value, true);
  });
  $("help-modal").addEventListener("click", (e) => {
    if (e.target === $("help-modal")) CueKey.closeHelp();
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") CueKey.closeHelp();
  });

  $("notation").addEventListener("click", (e) => {
    const btn = e.target.closest("button");
    if (!btn) return;
    state.notation = btn.dataset.value;
    for (const b of $("notation").children) b.classList.toggle("active", b === btn);
    renderTable();
    if (state.selectedId !== null) selectTrack(state.selectedId);
  });

  $("cue-mode").addEventListener("click", (e) => {
    const btn = e.target.closest("button");
    if (!btn) return;
    state.cueMode = btn.dataset.value;
    for (const b of $("cue-mode").children) b.classList.toggle("active", b === btn);
  });

  $("filter").addEventListener("input", (e) => { state.filter = e.target.value; renderTable(); });

  for (const th of document.querySelectorAll("th.sortable")) {
    th.addEventListener("click", () => {
      const key = th.dataset.sort;
      state.sortDir = state.sortKey === key ? -state.sortDir : 1;
      state.sortKey = key;
      for (const other of document.querySelectorAll("th .arrow")) other.remove();
      const arrow = document.createElement("span");
      arrow.className = "arrow";
      arrow.textContent = state.sortDir > 0 ? "▲" : "▼";
      th.appendChild(arrow);
      renderTable();
    });
  }

  // Native file drag & drop (pywebview exposes real paths on dropped files).
  const overlay = $("drop-overlay");
  let dragDepth = 0;
  document.addEventListener("dragenter", (e) => { e.preventDefault(); dragDepth++; overlay.classList.add("active"); });
  document.addEventListener("dragleave", (e) => { e.preventDefault(); if (--dragDepth <= 0) { dragDepth = 0; overlay.classList.remove("active"); } });
  document.addEventListener("dragover", (e) => e.preventDefault());
  document.addEventListener("drop", async (e) => {
    e.preventDefault();
    dragDepth = 0;
    overlay.classList.remove("active");
    const paths = [...e.dataTransfer.files]
      .map((f) => f.pywebviewFullPath)
      .filter(Boolean);
    if (paths.length) await window.pywebview.api.queue_paths(paths);
  });

  window.addEventListener("pywebviewready", async () => {
    const info = await window.pywebview.api.app_info();
    $("version").textContent = `v${info.version}`;
    // System language wins unless the user already picked one manually.
    if (!storedHelpLanguage()) setHelpLanguage(info.language === "es" ? "es" : "en");
  });
});
