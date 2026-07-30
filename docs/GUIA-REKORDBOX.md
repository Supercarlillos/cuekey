# Guía: cómo usar CueKey con rekordbox

## Cómo funciona (el concepto)

rekordbox guarda tu colección en una base de datos interna (`master.db`) que
ninguna aplicación externa puede modificar. El puente oficial que ofrece
rekordbox para intercambiar datos es su **formato XML**: un archivo de texto
que contiene la lista de tus pistas (con la ruta al archivo de audio, BPM,
tonalidad, cue points…) y tus playlists.

CueKey usa ese puente. **Nunca toca tu colección real**: lee el XML que tú
exportas, localiza cada archivo de audio en el disco, analiza el audio en sí
(tonalidad, BPM, energía, cue points) y escribe una **copia enriquecida** del
XML. Después rekordbox importa esa copia.

```
┌───────────┐  1. Exportar XML   ┌──────────┐  2. Analizar audio  ┌───────────────┐
│ rekordbox │ ─────────────────▶ │  CueKey  │ ──────────────────▶ │ XML enriquecido│
└───────────┘                    └──────────┘                     └───────┬───────┘
      ▲                                                                   │
      └────────────────── 3. Importar en rekordbox ◀──────────────────────┘
```

Qué añade CueKey a cada pista del XML:

| Campo XML | Qué es | Dónde lo ves en rekordbox |
|---|---|---|
| `Tonality` | Tonalidad detectada (`Am`) | Columna **Key** |
| `AverageBpm` | BPM detectado | Columna **BPM** |
| `Comments` | `8A - Energy 7` | Columna **Comentarios** |
| `POSITION_MARK` | Cue points | Memory cues (y hot cues A-H con `--hot-cues`) |

## Paso 1 — Exportar tu colección desde rekordbox

1. Abre rekordbox (modo Export).
2. Menú **File → Export Collection in xml format**.
3. Guárdalo donde quieras, por ejemplo `~/Desktop/collection.xml`.

Ese archivo contiene *referencias* a tus pistas, no el audio: tus archivos
de música no se copian ni se modifican.

## Paso 2 — Analizar con CueKey

### Con la app (DMG)

1. Abre **CueKey.app**.
2. (Opcional) elige la notación (`camelot` = `8A`), y marca *Hot cues (XML)*
   si además de memory cues quieres hot cues A-H.
3. Pulsa **rekordbox XML…**, elige tu `collection.xml` y el nombre del
   archivo de salida (por defecto `collection-cuekey.xml`).
4. Espera a que la barra de progreso termine. Verás cada pista en la tabla
   con su tonalidad, BPM, energía y nº de cues.

### Con el CLI

```bash
cuekey rekordbox ~/Desktop/collection.xml -o ~/Desktop/collection-cuekey.xml

# Solo una playlist (mucho más rápido para probar):
cuekey rekordbox collection.xml -o out.xml --playlist "Mi Sesión"

# Con hot cues y escribiendo también los tags de los archivos:
cuekey rekordbox collection.xml -o out.xml --hot-cues --tags

# Prueba rápida con las 5 primeras pistas:
cuekey rekordbox collection.xml -o out.xml --limit 5
```

El análisis tarda ~2-5 segundos por pista. Las pistas cuyo archivo no se
encuentre en el disco se saltan sin detener el proceso.

## Paso 3 — Importar el resultado en rekordbox

1. **Preferences → Advanced → pestaña Database → rekordbox xml**: en
   *Imported Library* selecciona tu `collection-cuekey.xml`.
2. **Preferences → View → Layout**: marca la casilla **rekordbox xml** para
   que aparezca en la barra lateral.
3. En la barra lateral verás el nodo **rekordbox xml** con tus pistas y
   playlists. Ahí ya se muestran Key, BPM y comentarios.
4. Para incorporar los datos a tu colección real, **arrastra las pistas (o
   playlists enteras) desde el nodo rekordbox xml hacia tu Colección**.

## Avisos importantes

- ⚠️ **Al importar una pista desde el XML, rekordbox reemplaza su
  información** (incluidos tus memory/hot cues previos) por la del XML.
  Prueba primero con una playlist pequeña o pistas nuevas.
- El XML enriquecido es un archivo nuevo: tu `collection.xml` original y tu
  base de datos de rekordbox quedan intactos hasta que tú arrastres algo.
- **Alternativa sin XML**: `cuekey analyze ~/Música/DJ --tags` escribe
  tonalidad, BPM y el comentario `8A - Energy 7` directamente en los tags de
  los archivos; rekordbox los lee al reanalizar/recargar la pista. Ojo: los
  **cue points solo pueden viajar por XML**, los tags no los soportan.
- La notación se elige con `--notation camelot|openkey|standard`. rekordbox
  muestra en la columna Key el texto tal cual (`Am` por defecto en
  `Tonality`; el `8A` va en el comentario).

## Mezcla armónica en 10 segundos

Con la rueda armónica (`8A`, `9B`…): mezcla entre pistas con el **mismo
número o adyacente manteniendo la letra** (`8A → 7A/8A/9A`), o **cambia de
letra con el mismo número** (`8A → 8B`) para pasar de menor a mayor. Usa la
energía 1-10 para planificar subidas y bajadas de intensidad en la sesión.
