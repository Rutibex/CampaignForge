from __future__ import annotations
from dataclasses import dataclass
from typing import List
from xml.sax.saxutils import escape

from .generator import Dungeon, Door

@dataclass
class SvgConfig:
    cell_size: int = 10
    margin: int = 12
    draw_room_ids: bool = True

def dungeon_to_svg(d: Dungeon, cfg: SvgConfig) -> str:
    w_px = d.width * cfg.cell_size + cfg.margin * 2
    h_px = d.height * cfg.cell_size + cfg.margin * 2

    def rect(x,y,w,h,fill):
        return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{fill}" />'

    parts: List[str] = []
    parts.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{w_px}" height="{h_px}" viewBox="0 0 {w_px} {h_px}">')
    parts.append(rect(0,0,w_px,h_px,"#141414"))

    # floors
    for y in range(d.height):
        for x in range(d.width):
            if d.grid[y][x] == 1:
                px = cfg.margin + x * cfg.cell_size
                py = cfg.margin + y * cfg.cell_size
                parts.append(rect(px,py,cfg.cell_size,cfg.cell_size,"#E1E1E1"))

    # room outlines
    parts.append('<g stroke="#505050" stroke-width="2" fill="none">')
    for r in d.rooms:
        px = cfg.margin + r.x * cfg.cell_size
        py = cfg.margin + r.y * cfg.cell_size
        parts.append(f'<rect x="{px}" y="{py}" width="{r.w*cfg.cell_size}" height="{r.h*cfg.cell_size}" />')
    parts.append('</g>')

    # doors
    parts.append('<g stroke="#1E1E1E" stroke-width="3" fill="none">')
    for door in d.doors:
        parts.append(_door_svg(cfg, door))
    parts.append('</g>')

    # room ids
    if cfg.draw_room_ids:
        parts.append('<g font-family="sans-serif" font-size="12" font-weight="700" fill="#282828">')
        for r in d.rooms:
            cx, cy = r.center
            x = cfg.margin + cx * cfg.cell_size + cfg.cell_size * 0.2
            y = cfg.margin + cy * cfg.cell_size + cfg.cell_size * 0.8
            parts.append(f'<text x="{x:.1f}" y="{y:.1f}">{escape(str(r.id))}</text>')
        parts.append('</g>')

    parts.append('</svg>')
    return "\n".join(parts)

def _door_svg(cfg: SvgConfig, door: Door) -> str:
    px = cfg.margin + door.x * cfg.cell_size
    py = cfg.margin + door.y * cfg.cell_size
    cx = px + cfg.cell_size / 2
    cy = py + cfg.cell_size / 2

    dash = ' stroke-dasharray="6 4"' if door.secret else ""
    if door.orientation == "V":
        x1, y1, x2, y2 = cx, py + 2, cx, py + cfg.cell_size - 2
    else:
        x1, y1, x2, y2 = px + 2, cy, px + cfg.cell_size - 2, cy

    return f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}"{dash} />'
