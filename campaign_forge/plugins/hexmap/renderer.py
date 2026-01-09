from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional

from PySide6.QtCore import QPointF, Qt, QRectF
from PySide6.QtGui import QBrush, QPen, QColor, QPolygonF, QImage, QPainter
from PySide6.QtWidgets import QGraphicsScene, QGraphicsPolygonItem

from .generator import HexCell, Coord, hex_label

# Optional SVG export
try:
    from PySide6.QtSvg import QSvgGenerator
    _HAS_SVG = True
except Exception:
    QSvgGenerator = None
    _HAS_SVG = False


def terrain_color(name: str) -> QColor:
    mapping = {
        # OSR
        "Plains": QColor(180, 220, 140),
        "Forest": QColor(80, 160, 90),
        "Hills": QColor(200, 190, 120),
        "Mountains": QColor(150, 150, 160),
        "Swamp": QColor(90, 120, 90),
        "Desert": QColor(230, 210, 140),
        "Water": QColor(120, 170, 220),

        # Space
        "Void": QColor(25, 25, 35),
        "Dust Belt": QColor(140, 120, 100),
        "Asteroids": QColor(110, 110, 120),
        "Nebula": QColor(160, 110, 170),
        "Ice": QColor(200, 230, 255),
        "Radiation Zone": QColor(170, 210, 90),
        "Derelict Field": QColor(90, 90, 95),

        # Underdark
        "Caverns": QColor(120, 120, 130),
        "Fungus Forest": QColor(120, 170, 130),
        "Chasm": QColor(50, 50, 60),
        "Ruined Tunnels": QColor(135, 125, 120),
        "Black Lake": QColor(40, 70, 90),
        "Lava": QColor(220, 90, 40),
        "Crystal Beds": QColor(160, 210, 230),
    }
    return mapping.get(name, QColor(200, 200, 200))


@dataclass
class RenderConfig:
    hex_size: int = 22
    show_grid: bool = True
    show_labels: bool = True
    show_poi: bool = True
    show_rivers: bool = True
    show_roads: bool = True


def hex_corners(center: QPointF, size: float) -> QPolygonF:
    import math
    pts = []
    for i in range(6):
        angle = math.radians(60 * i)
        x = center.x() + size * math.cos(angle)
        y = center.y() + size * math.sin(angle)
        pts.append(QPointF(x, y))
    return QPolygonF(pts)


def cell_center(q: int, r: int, size: float) -> QPointF:
    # odd-q vertical layout
    import math
    x = size * 1.5 * q
    y = size * math.sqrt(3) * (r + 0.5 * (q & 1))
    return QPointF(x, y)


class HexPolyItem(QGraphicsPolygonItem):
    """
    A polygon item that remembers its (q,r).
    """
    def __init__(self, q: int, r: int, poly: QPolygonF):
        super().__init__(poly)
        self.q = q
        self.r = r
        self.setFlag(QGraphicsPolygonItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsPolygonItem.ItemIsFocusable, True)


def build_scene(
    cells: Dict[Coord, HexCell],
    width: int,
    height: int,
    cfg: RenderConfig,
    rivers: Optional[List[List[Coord]]] = None,
    roads: Optional[List[List[Coord]]] = None
) -> QGraphicsScene:
    scene = QGraphicsScene()
    size = float(cfg.hex_size)

    pen_grid = QPen(QColor(60, 60, 60))
    pen_grid.setWidth(1)
    pen_none = QPen(Qt.NoPen)

    # Draw hexes
    for (q, r), c in cells.items():
        center = cell_center(q, r, size)
        poly = hex_corners(center, size)

        item = HexPolyItem(q, r, poly)
        item.setBrush(QBrush(terrain_color(c.terrain)))
        item.setPen(pen_grid if cfg.show_grid else pen_none)
        scene.addItem(item)

        if cfg.show_labels:
            label = hex_label(q, r)
            t = scene.addText(label)
            t.setDefaultTextColor(QColor(20, 20, 20))
            t.setScale(0.6)
            t.setPos(center.x() - size * 0.72, center.y() - size * 0.70)


        if c.settlement:
            # Settlement marker (bigger than POI dot)
            m = max(4.0, size * 0.18)
            marker = scene.addRect(
                center.x() - m,
                center.y() - m,
                m * 2,
                m * 2,
                QPen(QColor(60, 20, 20)),
                QBrush(QColor(120, 40, 40)),
            )
            marker.setZValue(11)

            # Short label (optional, uses first 6 chars)
            name = str(c.settlement.get("name", "")) if isinstance(c.settlement, dict) else ""
            if name:
                tl = scene.addText(name[:6])
                tl.setDefaultTextColor(QColor(255, 255, 255))
                tl.setScale(0.55)
                tl.setPos(center.x() - m, center.y() + m * 0.25)
                tl.setZValue(12)

        if cfg.show_poi and c.poi:
            dot_r = max(2.0, size * 0.12)
            dot = scene.addEllipse(
                center.x() - dot_r,
                center.y() - dot_r,
                dot_r * 2,
                dot_r * 2,
                QPen(QColor(20, 20, 20)),
                QBrush(QColor(20, 20, 20)),
            )
            dot.setZValue(10)

    # Overlays: rivers & roads
    if rivers and cfg.show_rivers:
        pen = QPen(QColor(40, 90, 200))
        pen.setWidth(3)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        for path in rivers:
            for a, b in zip(path, path[1:]):
                p1 = cell_center(a[0], a[1], size)
                p2 = cell_center(b[0], b[1], size)
                line = scene.addLine(p1.x(), p1.y(), p2.x(), p2.y(), pen)
                line.setZValue(20)

    if roads and cfg.show_roads:
        pen = QPen(QColor(90, 70, 40))
        pen.setWidth(2)
        pen.setStyle(Qt.SolidLine)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        for path in roads:
            for a, b in zip(path, path[1:]):
                p1 = cell_center(a[0], a[1], size)
                p2 = cell_center(b[0], b[1], size)
                line = scene.addLine(p1.x(), p1.y(), p2.x(), p2.y(), pen)
                line.setZValue(19)

    rect = scene.itemsBoundingRect()
    scene.setSceneRect(rect.adjusted(-20, -20, 20, 20))
    return scene


def scene_to_image(scene: QGraphicsScene) -> QImage:
    rect = scene.sceneRect()
    img = QImage(int(rect.width()), int(rect.height()), QImage.Format_ARGB32)
    img.fill(Qt.white)

    painter = QPainter(img)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.translate(-rect.left(), -rect.top())
    scene.render(painter, target=QRectF(rect), source=rect)
    painter.end()
    return img


def can_export_svg() -> bool:
    return _HAS_SVG


def scene_to_svg(scene: QGraphicsScene, path: str) -> None:
    if not _HAS_SVG:
        raise RuntimeError("QtSvg is not available in this PySide6 install.")

    rect = scene.sceneRect()
    gen = QSvgGenerator()
    gen.setFileName(path)
    gen.setSize(rect.size().toSize())
    gen.setViewBox(rect.toRect())
    gen.setTitle("Campaign Forge Hex Map")
    gen.setDescription("Generated by Campaign Forge")

    painter = QPainter(gen)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.translate(-rect.left(), -rect.top())
    scene.render(painter, target=QRectF(rect), source=rect)
    painter.end()
