from __future__ import annotations

from typing import Optional, Tuple

from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QLabel,
    QGraphicsView,
    QGraphicsScene,
)
from PySide6.QtGui import QPixmap, QImage, QPainter
from PySide6.QtCore import Qt, Signal

from .generator import ContinentModel


class _ClickableGraphicsView(QGraphicsView):
    clicked = Signal(int, int)  # (x, y) in map cell coords

    def __init__(self, parent=None):
        super().__init__(parent)
        self._model: Optional[ContinentModel] = None
        self._img_size: Optional[Tuple[int, int]] = None

        # Correct enum usage in PySide6
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)

        # Nice UX defaults
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)

    def set_model(self, model: Optional[ContinentModel]):
        self._model = model
        if model:
            self._img_size = (model.w, model.h)
        else:
            self._img_size = None

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        if not self._model or not self._img_size:
            return
        if event.button() != Qt.MouseButton.LeftButton:
            return
        pos = self.mapToScene(event.pos())
        x = int(pos.x())
        y = int(pos.y())
        if 0 <= x < self._model.w and 0 <= y < self._model.h:
            self.clicked.emit(x, y)

    def wheelEvent(self, event):
        # Ctrl+Wheel zoom; wheel alone scrolls as usual
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y()
            factor = 1.15 if delta > 0 else (1.0 / 1.15)
            self.scale(factor, factor)
            event.accept()
            return
        super().wheelEvent(event)


class ContinentPreviewWindow(QMainWindow):
    cell_clicked = Signal(int, int)

    def __init__(self, title: str = "Continent Preview", parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)

        self._scene = QGraphicsScene(self)

        self._view = _ClickableGraphicsView(self)
        self._view.setScene(self._scene)
        self._view.clicked.connect(self.cell_clicked.emit)

        self._status = QLabel("No map yet.")
        self._status.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.addWidget(self._view, 1)
        layout.addWidget(self._status, 0)

        self.setCentralWidget(central)
        self.resize(900, 700)

        self._has_pixmap = False

    def set_image(self, img: Optional[QImage], model: Optional[ContinentModel], status_text: str = ""):
        self._scene.clear()
        self._view.set_model(model)
        self._has_pixmap = False

        if img is None:
            self._status.setText(status_text or "No image.")
            return

        pm = QPixmap.fromImage(img)
        self._scene.addPixmap(pm)
        self._scene.setSceneRect(pm.rect())
        self._has_pixmap = True

        self.refresh_fit()
        self._status.setText(status_text or f"{pm.width()}×{pm.height()} cells")

    def refresh_fit(self):
        if not self._has_pixmap:
            return
        try:
            self._view.fitInView(self._scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
        except Exception:
            pass

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.refresh_fit()
