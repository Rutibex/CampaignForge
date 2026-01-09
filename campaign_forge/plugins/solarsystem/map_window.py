from __future__ import annotations

from typing import Any, Dict, Optional, Callable, Tuple
from PySide6.QtCore import Qt, QPointF, QRectF, QSize, QEvent, QPoint
from PySide6.QtGui import QBrush, QPen, QPainter, QImage
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QGraphicsView, QGraphicsScene,
    QGraphicsEllipseItem, QGraphicsTextItem, QHBoxLayout, QPushButton, QLabel
)

try:
    from PySide6.QtSvg import QSvgGenerator
except Exception:
    QSvgGenerator = None  # type: ignore

import math


class BodyItem(QGraphicsEllipseItem):
    def __init__(self, rect: QRectF, body_id: str):
        super().__init__(rect)
        self.body_id = body_id
        self.setFlag(QGraphicsEllipseItem.ItemIsSelectable, True)
        self.setAcceptHoverEvents(True)

    def hoverEnterEvent(self, event):
        self.setPen(QPen(Qt.white, 2))
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self.setPen(QPen(Qt.black, 1))
        super().hoverLeaveEvent(event)


class SolarSystemMapWindow(QMainWindow):
    """A lightweight orbital diagram (not a simulation)."""

    def __init__(self, system: Dict[str, Any], *, on_select: Optional[Callable[[str], None]] = None):
        super().__init__()
        self.setWindowTitle("Solar System Map")
        self.system = system
        self.on_select = on_select

        self.scene = QGraphicsScene()
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing)
        self.view.setDragMode(QGraphicsView.ScrollHandDrag)

        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)

        top = QHBoxLayout()
        self.lbl = QLabel(system.get("name", "Solar System"))
        self.btn_fit = QPushButton("Fit")
        self.btn_fit.clicked.connect(self.fit_view)
        top.addWidget(self.lbl)
        top.addStretch(1)
        top.addWidget(self.btn_fit)
        layout.addLayout(top)

        layout.addWidget(self.view, 1)

        self._body_items: Dict[str, BodyItem] = {}
        self._body_pos: Dict[str, QPointF] = {}

        self._draw_system()
        self.view.viewport().installEventFilter(self)

        # Click/drag discrimination (avoid selecting while panning)
        self._press_pos: Optional[QPoint] = None
        self._press_scene_pos: Optional[QPointF] = None

    def eventFilter(self, obj, event):
        et = event.type()

        # Record press position so we can distinguish click vs. pan.
        if et == QEvent.Type.MouseButtonPress and getattr(event, "button", None):
            if event.button() == Qt.LeftButton:
                self._press_pos = event.pos()
                self._press_scene_pos = self.view.mapToScene(self._press_pos)
            return False

        if et == QEvent.Type.MouseButtonRelease and getattr(event, "button", None):
            if event.button() != Qt.LeftButton:
                return False

            # If the mouse moved a lot, treat as a pan, not a click.
            if self._press_pos is not None:
                delta = event.pos() - self._press_pos
                if (abs(delta.x()) + abs(delta.y())) > 6:
                    self._press_pos = None
                    self._press_scene_pos = None
                    return False

            scene_pos = self.view.mapToScene(event.pos())
            items = self.scene.items(QRectF(scene_pos - QPointF(2, 2), QSize(4, 4)))

            chosen: Optional[str] = None
            for it in items:
                if isinstance(it, BodyItem):
                    chosen = it.body_id
                    # mirror selection visually
                    for _id, bi in self._body_items.items():
                        bi.setSelected(_id == chosen)
                    break

            if chosen and self.on_select:
                self.on_select(chosen)

            self._press_pos = None
            self._press_scene_pos = None
            return True

        return super().eventFilter(obj, event)

    def fit_view(self):
        self.view.fitInView(self.scene.itemsBoundingRect().adjusted(-40, -40, 40, 40), Qt.KeepAspectRatio)

    def _r_for_au(self, au: float) -> float:
        # AU -> pixels (log-ish), tuned for readability
        au = max(0.05, float(au))
        return 170.0 * (1.0 + 0.7 * (math.log10(au + 1.0) * 3.6))

    def _draw_system(self):
        self.scene.clear()
        self._body_items.clear()
        self._body_pos.clear()

        self.lbl.setText(self.system.get("name", "Solar System"))

        hz = self.system.get("habitable_zone", {})
        hz_in = float(hz.get("inner", 1.0) or 1.0)
        hz_out = float(hz.get("outer", 1.7) or 1.7)

        # Habitable zone bands
        r1 = self._r_for_au(hz_in)
        r2 = self._r_for_au(hz_out)
        hz_pen = QPen(Qt.darkGreen, 1, Qt.DashLine)
        self.scene.addEllipse(-r2, -r2, r2*2, r2*2, hz_pen)
        self.scene.addEllipse(-r1, -r1, r1*2, r1*2, hz_pen)

        # Primary star
        stars = self.system.get("stars", []) or [{}]
        primary = stars[0]
        star_item = self.scene.addEllipse(-16, -16, 32, 32, QPen(Qt.black, 1), QBrush(Qt.yellow))
        star_label = self.scene.addText(primary.get("name", "Star"))
        star_label.setDefaultTextColor(Qt.white)
        star_label.setPos(QPointF(22, -12))

        # Companion stars (schematic)
        for i, s in enumerate(stars[1:], start=1):
            off = QPointF(80 + i*30, -60 - i*20)
            self.scene.addEllipse(off.x()-10, off.y()-10, 20, 20, QPen(Qt.black, 1), QBrush(Qt.darkYellow))
            t = self.scene.addText(s.get("name", f"Companion {i+1}"))
            t.setDefaultTextColor(Qt.lightGray)
            t.setPos(off + QPointF(14, -8))

        # Belts
        for b in self.system.get("belts", []) or []:
            au = float(b.get("au", 0) or 0)
            rr = self._r_for_au(au)
            self.scene.addEllipse(-rr, -rr, rr*2, rr*2, QPen(Qt.darkGray, 1, Qt.DotLine))
            txt = self.scene.addText(b.get("name", "Belt"))
            txt.setDefaultTextColor(Qt.lightGray)
            txt.setPos(QPointF(rr+6, -10))

        planets = self.system.get("orbits", []) or []
        # evenly distribute angles
        n = max(1, len(planets))
        for i, p in enumerate(planets):
            au = float(p.get("au", 1.0) or 1.0)
            rr = self._r_for_au(au)
            self.scene.addEllipse(-rr, -rr, rr*2, rr*2, QPen(Qt.gray, 1))

            angle = (i * 360.0 / n) * math.pi / 180.0
            x = rr * math.cos(angle)
            y = rr * math.sin(angle)
            pos = QPointF(x, y)
            self._body_pos[p.get("id")] = pos

            cls = (p.get("class", {}) or {}).get("key", "")
            rad = 6
            if cls == "gas_giant": rad = 11
            if cls == "super_earth": rad = 8
            if cls in ("ringworld", "dyson"): rad = 9

            brush = QBrush(Qt.cyan if p.get("has_life") else Qt.lightGray)
            if p.get("inhabited"):
                brush = QBrush(Qt.magenta)
            if cls == "lava": brush = QBrush(Qt.red)
            if cls == "ice": brush = QBrush(Qt.blue)
            if cls == "gas_giant": brush = QBrush(Qt.darkYellow)

            item = BodyItem(QRectF(x-rad, y-rad, rad*2, rad*2), p.get("id"))
            item.setPen(QPen(Qt.black, 1))
            item.setBrush(brush)
            self.scene.addItem(item)
            self._body_items[p.get("id")] = item

            label = QGraphicsTextItem(p.get("name", "Planet"))
            label.setDefaultTextColor(Qt.white)
            label.setPos(QPointF(x+rad+4, y-rad))
            self.scene.addItem(label)

            moons = p.get("moons", []) or []
            if moons:
                for mi, m in enumerate(moons[:10]):
                    ma = (mi * 2*math.pi / max(1, min(10, len(moons))))
                    mx = x + (rad + 10) * math.cos(ma)
                    my = y + (rad + 10) * math.sin(ma)
                    mpos = QPointF(mx, my)
                    self._body_pos[m.get("id")] = mpos
                    mrad = 3
                    mbrush = QBrush(Qt.green if m.get("has_life") else Qt.gray)
                    if m.get("inhabited"):
                        mbrush = QBrush(Qt.magenta)
                    mitem = BodyItem(QRectF(mx-mrad, my-mrad, mrad*2, mrad*2), m.get("id"))
                    mitem.setPen(QPen(Qt.black, 1))
                    mitem.setBrush(mbrush)
                    self.scene.addItem(mitem)
                    self._body_items[m.get("id")] = mitem

        # Routes (abstract)
        for r in self.system.get("routes", []) or []:
            a = self._body_pos.get(r.get("from"))
            b = self._body_pos.get(r.get("to"))
            if not a or not b:
                continue
            kind = r.get("kind", "route")
            pen = QPen(Qt.darkCyan if kind == "trade_lane" else Qt.darkMagenta, 1, Qt.DashLine)
            self.scene.addLine(a.x(), a.y(), b.x(), b.y(), pen)

        self.fit_view()

    def select_body(self, body_id: str):
        it = self._body_items.get(body_id)
        if not it:
            return
        for item in self._body_items.values():
            item.setSelected(False)
        it.setSelected(True)
        self.view.centerOn(it)

    def render_png_bytes(self, *, width: int = 1600, height: int = 900) -> bytes:
        rect = self.scene.itemsBoundingRect().adjusted(-60, -60, 60, 60)
        img = QImage(QSize(width, height), QImage.Format_ARGB32)
        img.fill(Qt.black)
        painter = QPainter(img)
        painter.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing)
        self.scene.render(painter, target=QRectF(0, 0, width, height), source=rect)
        painter.end()

        from PySide6.QtCore import QBuffer, QByteArray
        arr = QByteArray()
        buf = QBuffer(arr)
        buf.open(QBuffer.WriteOnly)
        img.save(buf, "PNG")
        buf.close()
        return bytes(arr)

    def render_svg_bytes(self, *, width: int = 1600, height: int = 900) -> Optional[bytes]:
        if QSvgGenerator is None:
            return None
        from PySide6.QtCore import QBuffer, QByteArray
        arr = QByteArray()
        buf = QBuffer(arr)
        buf.open(QBuffer.WriteOnly)

        gen = QSvgGenerator()
        gen.setOutputDevice(buf)
        gen.setSize(QSize(width, height))
        gen.setViewBox(QRectF(0, 0, width, height))
        gen.setTitle(self.system.get("name", "Solar System"))

        painter = QPainter(gen)
        painter.fillRect(QRectF(0, 0, width, height), Qt.black)

        rect = self.scene.itemsBoundingRect().adjusted(-60, -60, 60, 60)
        self.scene.render(painter, target=QRectF(0, 0, width, height), source=rect)
        painter.end()

        buf.close()
        return bytes(arr)
