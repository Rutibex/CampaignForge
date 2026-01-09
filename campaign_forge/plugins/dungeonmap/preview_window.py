from __future__ import annotations

import base64
from typing import Optional, Callable, Dict

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QToolBar, QDockWidget, QVBoxLayout,
    QHBoxLayout, QLabel, QSlider, QCheckBox, QPushButton
)
from PySide6.QtCore import Qt, QByteArray
from PySide6.QtGui import QAction

from .map_widget import DungeonMapView
from .renderer import RenderConfig

class DungeonPreviewWindow(QMainWindow):
    """Detached preview window for the Dungeon Map plugin.

    This window hosts the shared DungeonMapView instance (reparented in/out),
    and provides view + layer controls.
    """

    def __init__(
        self,
        map_view: DungeonMapView,
        get_render_config: Callable[[], RenderConfig],
        set_render_config: Callable[[RenderConfig], None],
        on_request_dock_back: Callable[[], None],
        parent=None
    ):
        super().__init__(parent)
        self.setWindowTitle("Dungeon Map Preview")
        self._map_view = map_view
        self._get_cfg = get_render_config
        self._set_cfg = set_render_config
        self._dock_back = on_request_dock_back

        self._build_ui()

    def _build_ui(self) -> None:
        # Central widget is the map view
        self.setCentralWidget(self._map_view)

        # Toolbar for view controls
        tb = QToolBar("View")
        tb.setObjectName("DungeonMapPreview_ViewToolbar")
        tb.setMovable(True)
        self.addToolBar(tb)

        act_fit = QAction("Fit", self)
        act_fit.triggered.connect(self._map_view.fit_to_bounds)
        tb.addAction(act_fit)

        act_reset = QAction("Reset", self)
        act_reset.triggered.connect(self._map_view.reset_view)
        tb.addAction(act_reset)

        act_full = QAction("Fullscreen", self)
        act_full.setCheckable(True)
        act_full.triggered.connect(self._toggle_fullscreen)
        tb.addAction(act_full)

        act_top = QAction("Always on Top", self)
        act_top.setCheckable(True)
        act_top.triggered.connect(self._toggle_always_on_top)
        tb.addAction(act_top)

        act_dock = QAction("Dock Back", self)
        act_dock.triggered.connect(self._dock_back)
        tb.addAction(act_dock)

        # Zoom slider in toolbar
        zoom_wrap = QWidget()
        zl = QHBoxLayout(zoom_wrap)
        zl.setContentsMargins(8, 0, 8, 0)
        zl.addWidget(QLabel("Zoom"))
        self.zoom_slider = QSlider(Qt.Horizontal)
        self.zoom_slider.setRange(10, 800)   # 0.1x -> 8.0x
        self.zoom_slider.setValue(int(self._map_view.get_zoom() * 100))
        self.zoom_slider.valueChanged.connect(lambda v: self._map_view.set_zoom(v / 100.0))
        zl.addWidget(self.zoom_slider)
        tb.addWidget(zoom_wrap)

        # Layers dock
        self.layers_dock = QDockWidget("Layers", self)
        self.layers_dock.setObjectName("DungeonMapPreview_LayersDock")
        self.layers_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.addDockWidget(Qt.RightDockWidgetArea, self.layers_dock)

        panel = QWidget()
        v = QVBoxLayout(panel)
        v.setContentsMargins(8, 8, 8, 8)

        # Helpers
        self.chk_grid = QCheckBox("Grid")
        self.chk_axes = QCheckBox("Axes / scale")
        v.addWidget(self.chk_grid)
        v.addWidget(self.chk_axes)

        v.addWidget(QLabel(""))  # spacer

        # Layer toggles
        self.chk_rooms = QCheckBox("Rooms")
        self.chk_corridors = QCheckBox("Corridors")
        self.chk_doors = QCheckBox("Doors")
        self.chk_sdoors = QCheckBox("Secret doors")
        self.chk_labels = QCheckBox("Labels")
        self.chk_keys = QCheckBox("Keys")
        self.chk_traps = QCheckBox("Traps")
        self.chk_enc = QCheckBox("Encounters")
        self.chk_faction = QCheckBox("Faction control")

        for w in [
            self.chk_rooms, self.chk_corridors, self.chk_doors, self.chk_sdoors,
            self.chk_labels, self.chk_keys, self.chk_traps, self.chk_enc, self.chk_faction
        ]:
            v.addWidget(w)

        v.addStretch(1)
        self.layers_dock.setWidget(panel)

        # Seed initial checkbox state from render config
        self._load_from_cfg(self._get_cfg())

        # Wire up changes
        for chk in [
            self.chk_grid, self.chk_axes,
            self.chk_rooms, self.chk_corridors, self.chk_doors, self.chk_sdoors,
            self.chk_labels, self.chk_keys, self.chk_traps, self.chk_enc, self.chk_faction
        ]:
            chk.stateChanged.connect(self._apply_cfg)

    def _toggle_fullscreen(self, checked: bool) -> None:
        if checked:
            self.showFullScreen()
        else:
            self.showNormal()

    def _toggle_always_on_top(self, checked: bool) -> None:
        flags = self.windowFlags()
        if checked:
            flags = flags | Qt.WindowStaysOnTopHint
        else:
            flags = flags & ~Qt.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.show()

    def _load_from_cfg(self, cfg: RenderConfig) -> None:
        # Helpers
        self.chk_grid.setChecked(bool(cfg.draw_grid))
        self.chk_axes.setChecked(bool(getattr(cfg, "draw_axes", False)))

        # Layers
        self.chk_rooms.setChecked(bool(getattr(cfg, "show_rooms", True)))
        self.chk_corridors.setChecked(bool(getattr(cfg, "show_corridors", True)))
        self.chk_doors.setChecked(bool(getattr(cfg, "show_doors", True)))
        self.chk_sdoors.setChecked(bool(getattr(cfg, "show_secret_doors", True)))
        self.chk_labels.setChecked(bool(getattr(cfg, "show_labels", True)))
        self.chk_keys.setChecked(bool(getattr(cfg, "show_keys", False)))
        self.chk_traps.setChecked(bool(getattr(cfg, "show_traps", False)))
        self.chk_enc.setChecked(bool(getattr(cfg, "show_encounters", False)))
        self.chk_faction.setChecked(bool(getattr(cfg, "show_faction", False)))

    def _apply_cfg(self) -> None:
        cfg = self._get_cfg()

        cfg.draw_grid = self.chk_grid.isChecked()
        cfg.draw_axes = self.chk_axes.isChecked()

        cfg.show_rooms = self.chk_rooms.isChecked()
        cfg.show_corridors = self.chk_corridors.isChecked()
        cfg.show_doors = self.chk_doors.isChecked()
        cfg.show_secret_doors = self.chk_sdoors.isChecked()
        cfg.show_labels = self.chk_labels.isChecked()
        cfg.show_keys = self.chk_keys.isChecked()
        cfg.show_traps = self.chk_traps.isChecked()
        cfg.show_encounters = self.chk_enc.isChecked()
        cfg.show_faction = self.chk_faction.isChecked()

        self._set_cfg(cfg)

    # -------- Persistence helpers --------

    @staticmethod
    def qbytearray_to_b64(b: QByteArray) -> str:
        if not b:
            return ""
        return base64.b64encode(bytes(b)).decode("ascii")

    @staticmethod
    def b64_to_qbytearray(s: str) -> QByteArray:
        if not s:
            return QByteArray()
        try:
            return QByteArray(base64.b64decode(s.encode("ascii")))
        except Exception:
            return QByteArray()

    def export_window_state(self) -> dict:
        return {
            "geometry_b64": self.qbytearray_to_b64(self.saveGeometry()),
            "window_state_b64": self.qbytearray_to_b64(self.saveState()),
            "zoom": float(self._map_view.get_zoom()),
            "is_fullscreen": bool(self.isFullScreen()),
            "always_on_top": bool(self.windowFlags() & Qt.WindowStaysOnTopHint),
        }

    def apply_window_state(self, state: dict) -> None:
        state = state or {}
        try:
            g = self.b64_to_qbytearray(state.get("geometry_b64", ""))
            if not g.isEmpty():
                self.restoreGeometry(g)
            ws = self.b64_to_qbytearray(state.get("window_state_b64", ""))
            if not ws.isEmpty():
                self.restoreState(ws)
        except Exception:
            pass

        zoom = state.get("zoom", None)
        if isinstance(zoom, (int, float)):
            self._map_view.set_zoom(float(zoom))
            self.zoom_slider.setValue(int(float(zoom) * 100))

        if state.get("always_on_top", False):
            self._toggle_always_on_top(True)

        if state.get("is_fullscreen", False):
            self.showFullScreen()
