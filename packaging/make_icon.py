"""Generate the CueKey app icon (.icns).

Draws a macOS-style rounded square with a dark vertical gradient and a
12-segment harmonic color wheel with a glowing hub — rendered at 2x and
downscaled for antialiasing, then packed into an .icns via iconutil.

Usage: .venv/bin/python packaging/make_icon.py
"""

from __future__ import annotations

import colorsys
import math
import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

SIZE = 1024
SS = 2  # supersampling factor
S = SIZE * SS

BG_TOP = (26, 22, 46)
BG_BOTTOM = (10, 11, 16)


def segment_color(index: int) -> tuple[int, int, int]:
    r, g, b = colorsys.hsv_to_rgb(index / 12.0, 0.72, 0.95)
    return int(r * 255), int(g * 255), int(b * 255)


def rounded_mask(size: int, radius: int) -> Image.Image:
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=255)
    return mask


def gradient_background(size: int) -> Image.Image:
    img = Image.new("RGB", (size, size))
    for y in range(size):
        t = y / (size - 1)
        row = tuple(int(BG_TOP[i] + (BG_BOTTOM[i] - BG_TOP[i]) * t) for i in range(3))
        ImageDraw.Draw(img).line([(0, y), (size, y)], fill=row)
    return img


def draw_wheel(img: Image.Image) -> None:
    draw = ImageDraw.Draw(img)
    cx = cy = S // 2
    outer = int(S * 0.335)
    inner = int(S * 0.21)
    gap_deg = 3.5

    for index in range(12):
        start = index * 30 - 90 + gap_deg / 2
        end = (index + 1) * 30 - 90 - gap_deg / 2
        color = segment_color(index)
        draw.arc(
            [cx - outer, cy - outer, cx + outer, cy + outer],
            start=start, end=end, fill=color, width=outer - inner,
        )

    # Glowing hub with a cue-marker triangle.
    hub = int(S * 0.115)
    glow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse(
        [cx - hub * 1.7, cy - hub * 1.7, cx + hub * 1.7, cy + hub * 1.7],
        fill=(139, 92, 246, 110),
    )
    img.paste(Image.alpha_composite(img.convert("RGBA"), glow.filter(ImageFilter.GaussianBlur(S // 40))))

    draw = ImageDraw.Draw(img)
    draw.ellipse([cx - hub, cy - hub, cx + hub, cy + hub], fill=(236, 238, 244))
    tri = hub * 0.52
    points = [
        (cx - tri * 0.55, cy - tri * math.sin(math.pi / 3)),
        (cx - tri * 0.55, cy + tri * math.sin(math.pi / 3)),
        (cx + tri * 1.05, cy),
    ]
    draw.polygon(points, fill=(11, 12, 16))


def build_master() -> Image.Image:
    img = gradient_background(S)
    draw_wheel(img)
    img = img.resize((SIZE, SIZE), Image.LANCZOS)

    # macOS icon shape: rounded square with margin (Big Sur style grid).
    margin = int(SIZE * 0.09)
    content = SIZE - 2 * margin
    shaped = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    scaled = img.resize((content, content), Image.LANCZOS)
    mask = rounded_mask(content, radius=int(content * 0.225))
    shaped.paste(scaled, (margin, margin), mask)
    return shaped


def write_icns(master: Image.Image, output: Path) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        iconset = Path(tmp) / "CueKey.iconset"
        iconset.mkdir()
        for size in (16, 32, 64, 128, 256, 512):
            for scale in (1, 2):
                px = size * scale
                suffix = "" if scale == 1 else "@2x"
                master.resize((px, px), Image.LANCZOS).save(
                    iconset / f"icon_{size}x{size}{suffix}.png"
                )
        subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(output)], check=True)


if __name__ == "__main__":
    out = Path(__file__).parent / "icon.icns"
    master = build_master()
    write_icns(master, out)
    preview = Path(__file__).parent / "icon_preview.png"
    master.resize((256, 256), Image.LANCZOS).save(preview)
    print(f"wrote {out} ({out.stat().st_size // 1024} KB) and {preview}")
