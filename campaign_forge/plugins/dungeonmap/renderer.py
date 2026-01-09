from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple, Optional

from PySide6.QtGui import QImage, QPainter, QColor, QPen, QFont
from PySide6.QtCore import Qt, QRect

from .generator import Dungeon, Door, Room

@dataclass
class RenderConfig:
    cell_size: int = 10
    margin: int = 12

    # Overlays / helpers
    draw_grid: bool = False
    draw_axes: bool = False

    # Layers
    show_rooms: bool = True
    show_corridors: bool = True
    show_doors: bool = True
    show_secret_doors: bool = True
    show_labels: bool = True          # room id / name
    show_keys: bool = False           # room tag / key hints
    show_traps: bool = False
    show_encounters: bool = False
    show_faction: bool = False

def _hash_color(name: str, alpha: int = 70) -> QColor:
    # Deterministic but varied
    h = 2166136261
    for ch in name:
        h ^= ord(ch)
        h = (h * 16777619) & 0xFFFFFFFF
    r = 60 + (h & 0x7F)
    g = 60 + ((h >> 8) & 0x7F)
    b = 60 + ((h >> 16) & 0x7F)
    return QColor(r, g, b, alpha)

def render_dungeon_to_qimage(d: Dungeon, cfg: RenderConfig) -> QImage:
    w_px = d.width * cfg.cell_size + cfg.margin * 2
    h_px = d.height * cfg.cell_size + cfg.margin * 2

    img = QImage(w_px, h_px, QImage.Format_ARGB32)
    img.fill(QColor(20, 20, 20))

    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing, False)

    # Background / floors
    # cell_types:
    #   0 wall
    #   1 room floor
    #   2 corridor floor
    #   3 secret corridor floor
    #   4 cave floor (optional)
    cell_types = getattr(d, "cell_types", None)

    def draw_cell(x: int, y: int, color: QColor) -> None:
        px = cfg.margin + x * cfg.cell_size
        py = cfg.margin + y * cfg.cell_size
        p.fillRect(px, py, cfg.cell_size, cfg.cell_size, color)

    room_floor = QColor(230, 230, 230)
    corridor_floor = QColor(220, 220, 220)
    secret_corridor = QColor(210, 210, 210)
    cave_floor = QColor(205, 205, 205)

    for y in range(d.height):
        for x in range(d.width):
            is_floor = d.grid[y][x] == 1
            if not is_floor:
                continue

            if cell_types:
                t = cell_types[y][x]
                if t == 1 and not cfg.show_rooms:
                    continue
                if t in (2, 4) and not cfg.show_corridors:
                    continue
                if t == 3 and not cfg.show_corridors:
                    continue  # treat as corridor layer

                if t == 1:
                    draw_cell(x, y, room_floor)
                elif t == 2:
                    draw_cell(x, y, corridor_floor)
                elif t == 3:
                    draw_cell(x, y, secret_corridor)
                elif t == 4:
                    draw_cell(x, y, cave_floor)
                else:
                    draw_cell(x, y, corridor_floor)
            else:
                # Fallback: old dungeons have no per-cell typing
                # Treat all floor as corridor/room, obey corridor toggle only.
                if not (cfg.show_rooms or cfg.show_corridors):
                    continue
                draw_cell(x, y, corridor_floor)

    # Optional faction overlays (fills rooms)
    if cfg.show_faction:
        for r in d.rooms:
            ctrl = getattr(r, "control", "") or ""
            if not ctrl:
                continue
            px = cfg.margin + r.x * cfg.cell_size
            py = cfg.margin + r.y * cfg.cell_size
            w = r.w * cfg.cell_size
            h = r.h * cfg.cell_size
            p.fillRect(px, py, w, h, _hash_color(ctrl, alpha=70))

    # Optional grid lines
    if cfg.draw_grid:
        pen = QPen(QColor(0, 0, 0, 55))
        pen.setWidth(1)
        p.setPen(pen)
        for x in range(d.width + 1):
            px = cfg.margin + x * cfg.cell_size
            p.drawLine(px, cfg.margin, px, cfg.margin + d.height * cfg.cell_size)
        for y in range(d.height + 1):
            py = cfg.margin + y * cfg.cell_size
            p.drawLine(cfg.margin, py, cfg.margin + d.width * cfg.cell_size, py)

    # Room outlines
    if cfg.show_rooms:
        room_outline = QPen(QColor(80, 80, 80))
        room_outline.setWidth(2)
        p.setPen(room_outline)
        for r in d.rooms:
            rect = QRect(
                cfg.margin + r.x * cfg.cell_size,
                cfg.margin + r.y * cfg.cell_size,
                r.w * cfg.cell_size,
                r.h * cfg.cell_size,
            )
            p.drawRect(rect)

    # Corridor debug paths
    if getattr(cfg, "draw_corridor_paths", False):
        for c in d.corridors:
            pen = QPen(QColor(120, 120, 120) if not c.secret else QColor(150, 150, 150))
            pen.setWidth(2)
            if c.secret:
                pen.setStyle(Qt.DashLine)
            p.setPen(pen)
            for i in range(len(c.points) - 1):
                x1, y1 = c.points[i]
                x2, y2 = c.points[i + 1]
                p.drawLine(
                    cfg.margin + x1 * cfg.cell_size + cfg.cell_size // 2,
                    cfg.margin + y1 * cfg.cell_size + cfg.cell_size // 2,
                    cfg.margin + x2 * cfg.cell_size + cfg.cell_size // 2,
                    cfg.margin + y2 * cfg.cell_size + cfg.cell_size // 2,
                )

    # Doors
    if cfg.show_doors or cfg.show_secret_doors:
        for door in d.doors:
            if door.secret and not cfg.show_secret_doors:
                continue
            if (not door.secret) and not cfg.show_doors:
                continue
            _draw_door(p, door, cfg)

    # Labels / keys / content markers
    if cfg.show_labels or cfg.show_keys or cfg.show_traps or cfg.show_encounters:
        font = QFont()
        font.setPointSize(max(7, cfg.cell_size))
        p.setFont(font)

        for r in d.rooms:
            cx = cfg.margin + (r.x + r.w / 2) * cfg.cell_size
            cy = cfg.margin + (r.y + r.h / 2) * cfg.cell_size

            # Labels: show room id or name
            if cfg.show_labels:
                label = getattr(r, "name", "") or f"{r.id}"
                p.setPen(QPen(QColor(20, 20, 20)))
                p.drawText(int(cx - cfg.cell_size), int(cy), label)

            # Keys: show room tag as small text in corner
            if cfg.show_keys:
                tag = getattr(r, "tag", "") or ""
                if tag:
                    p.setPen(QPen(QColor(60, 60, 60)))
                    p.drawText(
                        cfg.margin + r.x * cfg.cell_size + 2,
                        cfg.margin + r.y * cfg.cell_size + cfg.cell_size - 2,
                        tag[:10],
                    )

            # Traps / Encounters markers
            if cfg.show_traps:
                trap = getattr(getattr(r, "contents", None), "trap", "") or ""
                if trap:
                    p.setPen(QPen(QColor(160, 30, 30)))
                    p.drawText(
                        cfg.margin + (r.x + r.w) * cfg.cell_size - cfg.cell_size,
                        cfg.margin + r.y * cfg.cell_size + cfg.cell_size,
                        "T",
                    )
            if cfg.show_encounters:
                enc = getattr(getattr(r, "contents", None), "encounter", "") or ""
                if enc:
                    p.setPen(QPen(QColor(30, 30, 160)))
                    p.drawText(
                        cfg.margin + (r.x + r.w) * cfg.cell_size - cfg.cell_size,
                        cfg.margin + (r.y + r.h) * cfg.cell_size - 2,
                        "E",
                    )

    # Axes overlay (simple)
    if cfg.draw_axes:
        p.setPen(QPen(QColor(240, 240, 240)))
        p.drawLine(cfg.margin, cfg.margin, cfg.margin + 30, cfg.margin)  # x-axis
        p.drawLine(cfg.margin, cfg.margin, cfg.margin, cfg.margin + 30)  # y-axis
        p.setPen(QPen(QColor(240, 240, 240)))
        p.drawText(cfg.margin + 34, cfg.margin + 10, "X")
        p.drawText(cfg.margin - 10, cfg.margin + 40, "Y")
        p.drawText(cfg.margin + 2, cfg.margin - 4, f"{cfg.cell_size}px/cell")

    p.end()
    return img

def _draw_door(p: QPainter, door: Door, cfg: RenderConfig) -> None:
    px = cfg.margin + door.x * cfg.cell_size
    py = cfg.margin + door.y * cfg.cell_size

    # Style based on secret + state
    pen = QPen(QColor(30, 30, 30))
    pen.setWidth(max(2, cfg.cell_size // 3))

    if door.secret:
        pen.setStyle(Qt.DashLine)

    # Door type color hint (subtle)
    dtype = getattr(door, "door_type", "wooden") or "wooden"
    if dtype == "iron":
        pen.setColor(QColor(40, 40, 40))
    elif dtype == "stone":
        pen.setColor(QColor(70, 70, 70))
    elif dtype == "portcullis":
        pen.setColor(QColor(20, 20, 20))
    elif dtype == "magical":
        pen.setColor(QColor(90, 40, 160))
    elif dtype == "organic":
        pen.setColor(QColor(80, 40, 40))
    elif dtype == "illusory":
        pen.setColor(QColor(120, 120, 120))

    p.setPen(pen)

    cx = px + cfg.cell_size // 2
    cy = py + cfg.cell_size // 2

    if door.orientation == "V":
        p.drawLine(cx, py + 2, cx, py + cfg.cell_size - 2)
    else:
        p.drawLine(px + 2, cy, px + cfg.cell_size - 2, cy)

    # Locked marker: small dot
    if getattr(door, "locked", False):
        p.setPen(QPen(QColor(0, 0, 0)))
        p.setBrush(QColor(0, 0, 0))
        p.drawEllipse(cx - 2, cy - 2, 4, 4)

    # Trapped marker: small X
    if getattr(door, "trapped", False):
        p.setPen(QPen(QColor(160, 30, 30)))
        p.drawLine(cx - 3, cy - 3, cx + 3, cy + 3)
        p.drawLine(cx - 3, cy + 3, cx + 3, cy - 3)
