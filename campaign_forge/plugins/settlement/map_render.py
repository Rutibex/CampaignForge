
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import math

from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QBrush, QPen, QPainterPath, QColor, QFont
from PySide6.QtWidgets import QGraphicsScene, QGraphicsEllipseItem, QGraphicsPathItem, QGraphicsSimpleTextItem, QGraphicsItem

from .generator import Settlement, District

@dataclass
class MapRenderOptions:
    show_districts: bool = True
    show_labels: bool = True
    show_roads: bool = True
    show_river: bool = True
    show_walls: bool = True
    show_landmarks: bool = True
    show_factions: bool = False

# A small, deterministic palette (fallback)
PALETTE = [
    QColor(0x8A, 0xB6, 0xD6),
    QColor(0xC8, 0xA2, 0xC8),
    QColor(0xB9, 0xD7, 0x7D),
    QColor(0xF2, 0xC1, 0x7D),
    QColor(0xF3, 0x8B, 0x8B),
    QColor(0xA7, 0xA7, 0xA7),
]

def _faction_color(index: int) -> QColor:
    return PALETTE[index % len(PALETTE)]

def build_scene(settlement: Settlement, opts: MapRenderOptions) -> QGraphicsScene:
    W, H = settlement.map_width, settlement.map_height
    scene = QGraphicsScene(0, 0, W, H)
    scene.setBackgroundBrush(QBrush(QColor(250, 248, 242)))

    # River
    if opts.show_river and settlement.river_path:
        path = QPainterPath()
        pts = [QPointF(x, y) for x, y in settlement.river_path]
        path.moveTo(pts[0])
        for p in pts[1:]:
            path.lineTo(p)
        river = QGraphicsPathItem(path)
        river.setPen(QPen(QColor(90, 140, 200), 18, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        river.setZValue(1)
        scene.addItem(river)

        river2 = QGraphicsPathItem(path)
        river2.setPen(QPen(QColor(120, 170, 230), 10, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        river2.setZValue(2)
        scene.addItem(river2)

    # Walls
    if opts.show_walls and settlement.has_walls:
        cx, cy = settlement.wall_center
        r = settlement.wall_radius
        wall = QGraphicsEllipseItem(cx - r, cy - r, r * 2, r * 2)
        wall.setPen(QPen(QColor(80, 60, 40), 6))
        wall.setBrush(Qt.NoBrush)
        wall.setZValue(3)
        scene.addItem(wall)

        gate = QGraphicsEllipseItem(cx - 14, cy - r - 10, 28, 20)
        gate.setBrush(QBrush(QColor(80, 60, 40)))
        gate.setPen(Qt.NoPen)
        gate.setZValue(4)
        scene.addItem(gate)

    # Roads (simple: connect each district to nearest 1-2 neighbors + center)
    if opts.show_roads and settlement.districts:
        roads = _compute_roads(settlement.districts)
        for (a, b) in roads:
            path = QPainterPath(QPointF(a.x, a.y))
            path.lineTo(QPointF(b.x, b.y))
            item = QGraphicsPathItem(path)
            item.setPen(QPen(QColor(140, 120, 90), 4, Qt.SolidLine, Qt.RoundCap))
            item.setZValue(5)
            scene.addItem(item)

    # Districts
    if opts.show_districts:
        for di, d in enumerate(settlement.districts):
            fill = QColor(240, 235, 220)
            stroke = QColor(60, 50, 40)

            if opts.show_factions and d.influence:
                # dominant faction decides fill
                dom = max(d.influence.items(), key=lambda kv: kv[1])[0]
                f_index = _faction_index(settlement, dom)
                c = _faction_color(f_index)
                fill = QColor(c.red(), c.green(), c.blue(), 120)

            ellipse = QGraphicsEllipseItem(d.x - d.r, d.y - d.r, d.r * 2, d.r * 2)
            ellipse.setBrush(QBrush(fill))
            ellipse.setPen(QPen(stroke, 3))
            ellipse.setZValue(10)
            ellipse.setData(0, d.id)  # used for click
            ellipse.setFlag(QGraphicsItem.ItemIsSelectable, True)
            scene.addItem(ellipse)

            if opts.show_landmarks and d.locations:
                # 2 landmark dots
                for li in range(min(2, len(d.locations))):
                    ang = (li / 2.0) * math.tau + 0.7
                    lx = d.x + math.cos(ang) * d.r * 0.35
                    ly = d.y + math.sin(ang) * d.r * 0.35
                    dot = QGraphicsEllipseItem(lx - 5, ly - 5, 10, 10)
                    dot.setBrush(QBrush(QColor(60, 50, 40)))
                    dot.setPen(Qt.NoPen)
                    dot.setZValue(11)
                    scene.addItem(dot)

            if opts.show_labels:
                label = QGraphicsSimpleTextItem(_short_label(d))
                font = QFont()
                font.setPointSize(10)
                font.setBold(True)
                label.setFont(font)
                label.setBrush(QBrush(QColor(30, 25, 20)))
                br = label.boundingRect()
                label.setPos(d.x - br.width()/2, d.y - br.height()/2)
                label.setZValue(12)
                scene.addItem(label)

    # Title
    title = QGraphicsSimpleTextItem(f"{settlement.name} — {settlement.settlement_type}")
    font = QFont()
    font.setPointSize(16)
    font.setBold(True)
    title.setFont(font)
    title.setBrush(QBrush(QColor(30, 25, 20)))
    title.setPos(18, 10)
    title.setZValue(50)
    scene.addItem(title)

    subtitle = QGraphicsSimpleTextItem(f"{settlement.terrain} • {settlement.population_band} • {settlement.age}")
    font2 = QFont()
    font2.setPointSize(11)
    subtitle.setFont(font2)
    subtitle.setBrush(QBrush(QColor(70, 60, 50)))
    subtitle.setPos(20, 36)
    subtitle.setZValue(50)
    scene.addItem(subtitle)

    return scene

def _short_label(d: District) -> str:
    # Strip kind suffix for compact labels
    s = d.name
    if "(" in s:
        s = s.split("(")[0].strip()
    return s

def _faction_index(settlement: Settlement, faction_id: str) -> int:
    for i, f in enumerate(settlement.factions):
        if f.id == faction_id:
            return i
    return 0

def _compute_roads(districts: List[District]) -> List[Tuple[District, District]]:
    # Connect each district to its nearest neighbor, plus connect all to a "centerish" district.
    roads = set()
    if not districts:
        return []
    # center district = closest to average point
    ax = sum(d.x for d in districts) / len(districts)
    ay = sum(d.y for d in districts) / len(districts)
    center = min(districts, key=lambda d: (d.x-ax)**2 + (d.y-ay)**2)

    for d in districts:
        # nearest neighbor
        nn = min([o for o in districts if o is not d], key=lambda o: (o.x-d.x)**2 + (o.y-d.y)**2, default=None)
        if nn:
            roads.add(tuple(sorted((d.id, nn.id))))
        if d is not center:
            roads.add(tuple(sorted((d.id, center.id))))

    # Convert back to objects
    by_id = {d.id: d for d in districts}
    out = []
    for a_id, b_id in roads:
        if a_id in by_id and b_id in by_id:
            out.append((by_id[a_id], by_id[b_id]))
    return out

def scene_to_svg(settlement: Settlement, opts: MapRenderOptions) -> str:
    # Lightweight SVG generator from the same geometry.
    W, H = settlement.map_width, settlement.map_height
    def esc(x: str) -> str:
        return (x or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    parts: List[str] = []
    parts.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">')
    parts.append('<rect x="0" y="0" width="100%" height="100%" fill="#FAF8F2"/>')

    # River
    if opts.show_river and settlement.river_path:
        pts = " ".join(f"{x:.1f},{y:.1f}" for x,y in settlement.river_path)
        parts.append(f'<polyline points="{pts}" fill="none" stroke="#5A8CC8" stroke-width="18" stroke-linecap="round" stroke-linejoin="round" opacity="0.9"/>')
        parts.append(f'<polyline points="{pts}" fill="none" stroke="#78AAE6" stroke-width="10" stroke-linecap="round" stroke-linejoin="round" opacity="0.95"/>')

    # Walls
    if opts.show_walls and settlement.has_walls:
        cx, cy = settlement.wall_center
        r = settlement.wall_radius
        parts.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="none" stroke="#503C28" stroke-width="6"/>')
        parts.append(f'<ellipse cx="{cx:.1f}" cy="{cy-r-0.0:.1f}" rx="14" ry="10" fill="#503C28"/>')

    # Roads
    if opts.show_roads and settlement.districts:
        for a,b in _compute_roads(settlement.districts):
            parts.append(f'<line x1="{a.x:.1f}" y1="{a.y:.1f}" x2="{b.x:.1f}" y2="{b.y:.1f}" stroke="#8C785A" stroke-width="4" stroke-linecap="round" opacity="0.85"/>')

    # Districts
    if opts.show_districts:
        for d in settlement.districts:
            fill = "#F0EBDC"
            if opts.show_factions and d.influence:
                dom = max(d.influence.items(), key=lambda kv: kv[1])[0]
                idx = _faction_index(settlement, dom)
                c = _faction_color(idx)
                fill = f'rgba({c.red()},{c.green()},{c.blue()},0.45)'
            parts.append(f'<circle cx="{d.x:.1f}" cy="{d.y:.1f}" r="{d.r:.1f}" fill="{fill}" stroke="#3C3228" stroke-width="3"/>')
            if opts.show_landmarks and d.locations:
                for li in range(min(2, len(d.locations))):
                    ang = (li / 2.0) * math.tau + 0.7
                    lx = d.x + math.cos(ang) * d.r * 0.35
                    ly = d.y + math.sin(ang) * d.r * 0.35
                    parts.append(f'<circle cx="{lx:.1f}" cy="{ly:.1f}" r="5" fill="#3C3228"/>')
            if opts.show_labels:
                label = esc(_short_label(d))
                parts.append(f'<text x="{d.x:.1f}" y="{d.y:.1f}" font-family="sans-serif" font-size="12" font-weight="700" fill="#1E1914" text-anchor="middle" dominant-baseline="middle">{label}</text>')

    # Title
    parts.append(f'<text x="18" y="28" font-family="sans-serif" font-size="20" font-weight="800" fill="#1E1914">{esc(settlement.name)} — {esc(settlement.settlement_type)}</text>')
    parts.append(f'<text x="20" y="52" font-family="sans-serif" font-size="13" fill="#463C32">{esc(settlement.terrain)} • {esc(settlement.population_band)} • {esc(settlement.age)}</text>')

    parts.append('</svg>')
    return "\n".join(parts)
