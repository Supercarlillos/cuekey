/* In-app help content, Spanish and English. Injected into #help-body. */

"use strict";

const HELP_CONTENT = {
  es: `
<h3>Qué hace CueKey</h3>
<p>Analiza el audio de tus pistas y detecta, para cada una:</p>
<ul>
  <li><b>Tonalidad</b> — en notación Camelot (<code>8A</code>), Open Key (<code>1m</code>) o clásica (<code>Am</code>). Cambia la notación con el selector superior sin re-analizar.</li>
  <li><b>BPM</b> — refinado sobre el grid real de beats. Los tempos de estudio salen exactos (128); los decimales solo aparecen cuando son reales (vinilo, directos).</li>
  <li><b>Energía 1-10</b> — intensidad percibida (volumen, densidad rítmica, graves, tempo) para planificar la curva de tu sesión.</li>
  <li><b>Cue points</b> — hasta 8 puntos en cambios estructurales (intro, drop, breakdown), ajustados al beat.</li>
</ul>

<h3>Files / Folder + Analyze</h3>
<p>Añade archivos o carpetas (botones o arrastrando a la ventana) y pulsa <b>▶ Analyze</b>:</p>
<ul>
  <li>Tu audio <b>nunca se modifica</b> — la música suena exactamente igual.</li>
  <li>Con <b>Write tags</b> activado, los resultados se guardan en los metadatos de cada archivo: tonalidad (<code>TKEY</code>/<code>INITIALKEY</code>), BPM (<code>TBPM</code>) y un comentario tipo <code>8A - Energy 7</code>. No se crea ningún archivo nuevo.</li>
  <li>rekordbox lee esos tags al añadir la pista o con clic derecho → <i>Reload Tags</i>.</li>
  <li>Los <b>cue points solo se muestran en pantalla</b> en este flujo: los formatos de audio no pueden guardarlos. Para llevarlos a rekordbox usa el flujo XML.</li>
  <li><b>Rendimiento</b>: el análisis reparte las pistas entre los núcleos del procesador, y los resultados se guardan en una caché local — re-analizar pistas ya procesadas es instantáneo. La caché se invalida sola si el archivo cambia o el algoritmo mejora.</li>
</ul>

<h3>Flujo rekordbox XML (paso a paso)</h3>
<ol>
  <li>En rekordbox: <code>File → Export Collection in xml format</code>.</li>
  <li>En CueKey: pulsa <b>⟳ rekordbox XML</b>, elige ese archivo y dónde guardar el resultado. CueKey nunca toca tu colección real: trabaja sobre una copia enriquecida.</li>
  <li>En rekordbox: <code>Preferences → Advanced → Database → rekordbox xml</code> → selecciona el XML generado, y activa la vista en <code>Preferences → View → Layout → rekordbox xml</code>.</li>
  <li>Arrastra pistas o playlists desde el nodo <i>rekordbox xml</i> hacia tu colección.</li>
</ol>
<table>
  <tr><th>Campo</th><th>Dónde lo ves en rekordbox</th></tr>
  <tr><td>Tonalidad</td><td>Columna <b>Key</b></td></tr>
  <tr><td>BPM</td><td>Columna <b>BPM</b></td></tr>
  <tr><td><code>8A - Energy 7</code></td><td>Columna <b>Comentarios</b></td></tr>
  <tr><td>Cue points</td><td>Memory cues (+ hot cues A-H con <b>Hot cues</b>)</td></tr>
</table>

<h3>Tus cues existentes</h3>
<ul>
  <li><b>Keep</b> (por defecto): tus hot cues y memory cues se conservan intactos. Los de CueKey se añaden como memory cues extra, omitiendo los que caigan a menos de 1 segundo de una marca tuya, y los hot cues solo rellenan huecos libres (A-H).</li>
  <li><b>Replace</b>: descarta todo lo existente y regenera los cues desde cero.</li>
  <li>Ojo: al arrastrar una pista desde el XML, rekordbox reemplaza su información por la del XML (comportamiento de rekordbox). Con <i>Keep</i> no pierdes nada; prueba primero con una playlist pequeña.</li>
</ul>

<h3>Pausar o cancelar un análisis</h3>
<ul>
  <li>Durante cualquier análisis aparecen <b>⏸ Pause</b> y <b>✕ Cancel</b> junto a la barra de progreso.</li>
  <li>Ambos hacen efecto <b>al terminar la pista en curso</b> (unos segundos).</li>
  <li><b>Pause / Resume</b> congela el análisis sin perder nada — puedes dejarlo pausado el tiempo que quieras.</li>
  <li><b>Cancel</b> en el flujo XML <b>guarda el XML parcial</b>: las pistas ya analizadas quedan enriquecidas y el resto se mantiene tal cual estaba en tu colección. En el flujo de archivos, los tags ya escritos se conservan.</li>
</ul>

<h3>Mezcla armónica en 10 segundos</h3>
<p>Con la rueda: mezcla entre tonalidades con el <b>mismo número o adyacente manteniendo la letra</b> (<span class="pill-inline" style="background:hsl(210 52% 62%)">8A</span> → 7A / 8A / 9A), o <b>cambia de letra con el mismo número</b> (8A → 8B) para pasar de menor a mayor. Al seleccionar una pista, la rueda ilumina sus compatibles y la fila <b>MIX WITH</b> te las lista. Usa la energía para construir subidas y bajadas.</p>

<h3>Apoyar el proyecto ♥</h3>
<p>CueKey es gratuito y sin uso comercial. Si te resulta útil, puedes apoyar al creador y la evolución del producto con el botón <b>♥</b> (abajo a la izquierda): acepta PayPal y tarjeta vía Ko-fi, o Bitcoin.</p>

<h3>Problemas frecuentes</h3>
<ul>
  <li><b>✕ "file not found"</b> — el XML apunta a una ruta que ya no existe (archivo movido, borrado o disco externo desconectado). Esa lista te dice qué rutas de tu colección están rotas.</li>
  <li><b>La primera vez en otro Mac</b> — la app no está firmada por Apple: ábrela con clic derecho → <i>Abrir</i>.</li>
  <li><b>Un BPM o tonalidad no te cuadra</b> — puede pasar en pistas con tempo variable o armonía ambigua; compara con tu oído y repórtalo en el repositorio.</li>
</ul>
<p class="dim">CueKey es un proyecto open source independiente, sin afiliación con ningún software comercial de DJ. "rekordbox" es una marca de AlphaTheta Corporation, citada solo para describir interoperabilidad.</p>
`,
  en: `
<h3>What CueKey does</h3>
<p>It analyzes the audio of your tracks and detects, for each one:</p>
<ul>
  <li><b>Musical key</b> — in Camelot (<code>8A</code>), Open Key (<code>1m</code>) or classic (<code>Am</code>) notation. Switch notation from the top selector without re-analyzing.</li>
  <li><b>BPM</b> — refined against the actual beat grid. Studio tempos come out exact (128); decimals only appear when they are real (vinyl, live recordings).</li>
  <li><b>Energy 1-10</b> — perceived intensity (loudness, rhythmic density, bass, tempo) to plan your set's curve.</li>
  <li><b>Cue points</b> — up to 8 points at structural changes (intro, drop, breakdown), snapped to the beat.</li>
</ul>

<h3>Files / Folder + Analyze</h3>
<p>Add files or folders (buttons or drag &amp; drop onto the window) and press <b>▶ Analyze</b>:</p>
<ul>
  <li>Your audio is <b>never modified</b> — the music sounds exactly the same.</li>
  <li>With <b>Write tags</b> enabled, results are stored in each file's metadata: key (<code>TKEY</code>/<code>INITIALKEY</code>), BPM (<code>TBPM</code>) and a comment like <code>8A - Energy 7</code>. No new files are created.</li>
  <li>rekordbox reads those tags when you add the track, or via right click → <i>Reload Tags</i>.</li>
  <li><b>Cue points are display-only</b> in this flow: audio formats cannot store them. Use the XML flow to bring cues into rekordbox.</li>
  <li><b>Performance</b>: analysis spreads tracks across your CPU cores, and results are stored in a local cache — re-analyzing already-processed tracks is instant. The cache self-invalidates when a file changes or the algorithm improves.</li>
</ul>

<h3>rekordbox XML workflow (step by step)</h3>
<ol>
  <li>In rekordbox: <code>File → Export Collection in xml format</code>.</li>
  <li>In CueKey: press <b>⟳ rekordbox XML</b>, pick that file and where to save the result. CueKey never touches your real collection: it works on an enriched copy.</li>
  <li>In rekordbox: <code>Preferences → Advanced → Database → rekordbox xml</code> → select the generated XML, and enable the view in <code>Preferences → View → Layout → rekordbox xml</code>.</li>
  <li>Drag tracks or playlists from the <i>rekordbox xml</i> node into your collection.</li>
</ol>
<table>
  <tr><th>Field</th><th>Where it shows in rekordbox</th></tr>
  <tr><td>Key</td><td><b>Key</b> column</td></tr>
  <tr><td>BPM</td><td><b>BPM</b> column</td></tr>
  <tr><td><code>8A - Energy 7</code></td><td><b>Comments</b> column</td></tr>
  <tr><td>Cue points</td><td>Memory cues (+ hot cues A-H with <b>Hot cues</b>)</td></tr>
</table>

<h3>Your existing cues</h3>
<ul>
  <li><b>Keep</b> (default): your hot cues and memory cues are preserved untouched. CueKey's cues are added as extra memory cues, skipping any within 1 second of your marks, and hot cues only fill free slots (A-H).</li>
  <li><b>Replace</b>: discards everything and regenerates cues from scratch.</li>
  <li>Note: when you drag a track from the XML, rekordbox replaces its info with the XML's (that is rekordbox behavior). With <i>Keep</i> you lose nothing; try a small playlist first.</li>
</ul>

<h3>Pausing or cancelling an analysis</h3>
<ul>
  <li>While any analysis runs, <b>⏸ Pause</b> and <b>✕ Cancel</b> appear next to the progress bar.</li>
  <li>Both take effect <b>after the current track finishes</b> (a few seconds).</li>
  <li><b>Pause / Resume</b> freezes the analysis without losing anything — you can leave it paused as long as you like.</li>
  <li><b>Cancel</b> in the XML flow <b>saves a partial XML</b>: already-analyzed tracks stay enriched and the rest remain exactly as they were in your collection. In the files flow, tags already written are kept.</li>
</ul>

<h3>Harmonic mixing in 10 seconds</h3>
<p>On the wheel: mix between keys with the <b>same or adjacent number keeping the letter</b> (<span class="pill-inline" style="background:hsl(210 52% 62%)">8A</span> → 7A / 8A / 9A), or <b>swap the letter at the same number</b> (8A → 8B) to move between minor and major. Selecting a track lights up its compatible keys on the wheel and lists them under <b>MIX WITH</b>. Use energy to build and release intensity.</p>

<h3>Support the project ♥</h3>
<p>CueKey is free and noncommercial. If you find it useful, you can support the creator and the evolution of the product with the <b>♥</b> button (bottom left): PayPal and cards via Ko-fi, or Bitcoin.</p>

<h3>Troubleshooting</h3>
<ul>
  <li><b>✕ "file not found"</b> — the XML points to a path that no longer exists (moved or deleted file, disconnected external drive). That list tells you which paths in your collection are broken.</li>
  <li><b>First launch on another Mac</b> — the app is not Apple-signed: open it with right click → <i>Open</i>.</li>
  <li><b>A BPM or key looks off</b> — can happen with variable-tempo tracks or ambiguous harmony; trust your ears and report it on the repository.</li>
</ul>
<p class="dim">CueKey is an independent open-source project, not affiliated with any commercial DJ software. "rekordbox" is a trademark of AlphaTheta Corporation, referenced only to describe interoperability.</p>
`,
};
