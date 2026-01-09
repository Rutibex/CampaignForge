# -------------------------
# exports.py
# -------------------------
from __future__ import annotations
from typing import Optional
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
except Exception:
    Image = None

from .generator import CavernResult

def export_png(result: CavernResult, path: Path, cell_px: int = 8, show_biome: bool = False) -> None:
    if Image is None:
        raise RuntimeError("Pillow (PIL) not available. Install pillow to export PNG.")

    w = result.width * cell_px
    h = result.height * cell_px
    img = Image.new("RGB", (w, h), (0, 0, 0))
    draw = ImageDraw.Draw(img)

    biome_colors = {
        "Limestone": (130, 130, 130),
        "Fungal": (120, 80, 150),
        "Crystal": (120, 180, 220),
        "Flooded": (70, 110, 180),
        "Volcanic": (170, 80, 60),
        "Bonefield": (170, 170, 140),
        "Slime": (90, 160, 90),
        "Ruins": (150, 120, 90),
    }

    for y in range(result.height):
        for x in range(result.width):
            cell = result.grid[y][x]
            if cell == 0:
                color = (20, 20, 20)
            else:
                if show_biome:
                    b = result.biome_grid[y][x]
                    color = biome_colors.get(b, (160, 160, 160))
                else:
                    color = (180, 180, 180)
            x0, y0 = x * cell_px, y * cell_px
            draw.rectangle([x0, y0, x0 + cell_px - 1, y0 + cell_px - 1], fill=color)

    img.save(str(path))

def export_svg(result: CavernResult, path: Path, cell_px: int = 10, show_biome: bool = True) -> None:
    # Simple SVG: rects per cell (fine for small/medium maps)
    biome_colors = {
        "Limestone": "#808080",
        "Fungal": "#7a4f9a",
        "Crystal": "#7bb6d6",
        "Flooded": "#466cb4",
        "Volcanic": "#b35a44",
        "Bonefield": "#b0b08a",
        "Slime": "#5aa05a",
        "Ruins": "#9a7a5a",
    }

    w = result.width * cell_px
    h = result.height * cell_px
    parts = []
    parts.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">')
    parts.append('<rect x="0" y="0" width="100%" height="100%" fill="#000"/>')

    for y in range(result.height):
        for x in range(result.width):
            cell = result.grid[y][x]
            if cell == 0:
                fill = "#141414"
            else:
                if show_biome:
                    b = result.biome_grid[y][x]
                    fill = biome_colors.get(b, "#b0b0b0")
                else:
                    fill = "#b0b0b0"
            rx, ry = x * cell_px, y * cell_px
            parts.append(f'<rect x="{rx}" y="{ry}" width="{cell_px}" height="{cell_px}" fill="{fill}" />')

    parts.append("</svg>")
    path.write_text("\n".join(parts), encoding="utf-8")

def export_key_md(result: CavernResult, path: Path, title: str = "Cavern Key") -> None:
    lines = []
    lines.append(f"# {title}")
    lines.append("")
    lines.append(f"- **Seed:** `{result.seed}`")
    lines.append(f"- **Size:** {result.width}×{result.height}")
    lines.append(f"- **Regions:** {len(result.regions)}")
    lines.append("")
    lines.append("## Regions")
    lines.append("")
    for r in result.regions:
        x0, y0, x1, y1 = r.bbox
        lines.append(f"### R{r.id}: {r.name}")
        lines.append(f"- **Type:** {r.kind}")
        lines.append(f"- **Biome:** {r.biome}")
        lines.append(f"- **Cells:** {r.size}")
        lines.append(f"- **BBox:** ({x0},{y0})–({x1},{y1})")
        lines.append(f"- **Exits (approx):** {r.exits}")
        lines.append("")
        lines.append("**GM Notes:**")
        lines.append("- What’s here?")
        lines.append("- Why does it matter?")
        lines.append("- What changes if the party lingers?")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")