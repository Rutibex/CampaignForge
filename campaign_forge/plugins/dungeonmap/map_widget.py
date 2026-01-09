from __future__ import annotations

from typing import Optional, Callable

from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QPixmap, QImage
from PySide6.QtCore import Qt, QRect, QPoint, QPointF

from .generator import Dungeon, Room
from .renderer import RenderConfig, render_dungeon_to_qimage

class DungeonMapView(QWidget):
    """Interactive map preview with click-to-select, pan and zoom.

    - Left click: select room
    - Right drag (or middle drag): pan
    - Mouse wheel: zoom
    """

    def __init__(self, on_room_selected: Callable[[Optional[Room]], None]):
        super().__init__()
        self.setMinimumSize(320, 240)
        self.setMouseTracking(True)

        self._on_room_selected = on_room_selected
        self._dungeon: Optional[Dungeon] = None
        self._render_cfg = RenderConfig()
        self._img: Optional[QImage] = None
        self._pix: Optional[QPixmap] = None

        self._selected_room_id: Optional[int] = None

        # View transform
        self._zoom: float = 1.0
        self._pan = QPointF(0.0, 0.0)
        self._panning = False
        self._pan_start = QPoint()

    # ---------- Public API ----------

    def set_dungeon(self, d: Optional[Dungeon], render_cfg: Optional[RenderConfig] = None) -> None:
        self._dungeon = d
        if render_cfg is not None:
            self._render_cfg = render_cfg
        self._rerender()
        self.update()

    def set_render_config(self, cfg: RenderConfig) -> None:
        self._render_cfg = cfg
        self._rerender()
        self.update()

    def get_zoom(self) -> float:
        return float(self._zoom)

    def set_zoom(self, zoom: float) -> None:
        self._zoom = max(0.1, min(zoom, 8.0))
        self.update()

    def reset_view(self) -> None:
        self._zoom = 1.0
        self._pan = QPointF(0.0, 0.0)
        self.update()

    def fit_to_bounds(self) -> None:
        if not self._pix:
            return
        w = max(1, self.width())
        h = max(1, self.height())
        sx = w / self._pix.width()
        sy = h / self._pix.height()
        self._zoom = max(0.1, min(min(sx, sy), 8.0))
        self._pan = QPointF(0.0, 0.0)
        self.update()

    def set_selected_room(self, room: Optional[Room]) -> None:
        self._selected_room_id = room.id if room else None
        self.update()

    # ---------- Internals ----------

    def _rerender(self) -> None:
        if not self._dungeon:
            self._img = None
            self._pix = None
            return
        self._img = render_dungeon_to_qimage(self._dungeon, self._render_cfg)
        self._pix = QPixmap.fromImage(self._img)

    def _draw_placeholder(self, p: QPainter) -> None:
        p.fillRect(self.rect(), Qt.black)
        p.setPen(Qt.white)
        p.drawText(self.rect(), Qt.AlignCenter, "Generate a dungeon to preview it.")

    def _image_target_rect(self) -> Optional[QRect]:
        if not self._pix:
            return None
        w = int(self._pix.width() * self._zoom)
        h = int(self._pix.height() * self._zoom)
        x = int((self.width() - w) / 2 + self._pan.x())
        y = int((self.height() - h) / 2 + self._pan.y())
        return QRect(x, y, w, h)

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.SmoothPixmapTransform, True)

        if not self._pix:
            self._draw_placeholder(p)
            return

        target = self._image_target_rect()
        if not target:
            self._draw_placeholder(p)
            return

        p.fillRect(self.rect(), Qt.black)
        p.drawPixmap(target, self._pix)

        # Highlight selected room
        if self._dungeon and self._selected_room_id is not None:
            room = next((r for r in self._dungeon.rooms if r.id == self._selected_room_id), None)
            if room:
                rc = self._render_cfg
                room_px_x = rc.margin + room.x * rc.cell_size
                room_px_y = rc.margin + room.y * rc.cell_size
                room_px_w = room.w * rc.cell_size
                room_px_h = room.h * rc.cell_size

                sx = target.width() / self._pix.width()
                sy = target.height() / self._pix.height()

                hx = target.x() + int(room_px_x * sx)
                hy = target.y() + int(room_px_y * sy)
                hw = int(room_px_w * sx)
                hh = int(room_px_h * sy)

                from PySide6.QtGui import QColor, QPen
                p.setPen(QPen(QColor(255, 200, 80), 3))
                p.drawRect(QRect(hx, hy, hw, hh))

    def wheelEvent(self, ev):
        # zoom around cursor
        delta = ev.angleDelta().y()
        if delta == 0 or not self._pix:
            return

        old_zoom = self._zoom
        factor = 1.15 if delta > 0 else 1 / 1.15
        self._zoom = max(0.1, min(old_zoom * factor, 8.0))

        # Adjust pan so the point under cursor stays roughly in place
        pos = ev.position()
        if old_zoom != 0:
            self._pan = self._pan + (pos - QPointF(self.width() / 2, self.height() / 2)) * (1 - self._zoom / old_zoom)

        self.update()

    def mousePressEvent(self, ev):
        if ev.button() in (Qt.RightButton, Qt.MiddleButton):
            self._panning = True
            self._pan_start = ev.pos()
            ev.accept()
            return

        if ev.button() == Qt.LeftButton:
            room = self._hit_test_room(ev.pos())
            self._on_room_selected(room)
            ev.accept()
            return

        super().mousePressEvent(ev)

    def mouseMoveEvent(self, ev):
        if self._panning:
            delta = ev.pos() - self._pan_start
            self._pan_start = ev.pos()
            self._pan = self._pan + QPointF(delta.x(), delta.y())
            self.update()
            ev.accept()
            return
        super().mouseMoveEvent(ev)

    def mouseReleaseEvent(self, ev):
        if ev.button() in (Qt.RightButton, Qt.MiddleButton) and self._panning:
            self._panning = False
            ev.accept()
            return
        super().mouseReleaseEvent(ev)

    def _hit_test_room(self, pos: QPoint) -> Optional[Room]:
        if not self._pix or not self._dungeon:
            return None

        target = self._image_target_rect()
        if not target or not target.contains(pos):
            return None

        # Convert widget pixels -> image pixels
        px = (pos.x() - target.x()) * (self._pix.width() / target.width())
        py = (pos.y() - target.y()) * (self._pix.height() / target.height())

        rc = self._render_cfg
        cell_x = int((px - rc.margin) // rc.cell_size)
        cell_y = int((py - rc.margin) // rc.cell_size)

        for r in self._dungeon.rooms:
            if r.contains_cell(cell_x, cell_y):
                return r
        return None
