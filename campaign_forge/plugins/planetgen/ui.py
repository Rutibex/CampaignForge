from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
import math
import json
import time

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox, QSpinBox,
    QDoubleSpinBox, QGroupBox, QFormLayout, QCheckBox, QTextEdit, QMessageBox,
    QMainWindow, QDockWidget, QListWidget, QListWidgetItem, QSplitter, QFrame,
    QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QStatusBar
)
from PySide6.QtCore import Qt, QPointF, QRectF, QTimer, Signal, QObject
from PySide6.QtGui import QImage, QPixmap, QPainter, QColor, QPen, QBrush, QMouseEvent, QAction

from .generator import PlanetGenConfig, generate_world, PlanetWorld
from .exports import save_png, save_json, build_atlas_markdown


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _rgb(rgb):
    return QColor(int(rgb[0]), int(rgb[1]), int(rgb[2]))


def _clamp(v: float, lo: float, hi: float) -> float:
    return lo if v < lo else hi if v > hi else v


class PlanetMapView(QGraphicsView):
    """
    Interactive map view with click-to-inspect and simple edit modes.
    """
    hovered = Signal(int, int)  # x,y
    clicked = Signal(int, int)  # x,y
    painted = Signal(int, int, str, float)  # x,y, mode, amount

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        self._scale = 1.0
        self._dragging = False
        self._last_pos = None
        self.edit_mode = "inspect"   # inspect | raise | lower | paint_biome | place_poi
        self.paint_biome_id = "temperate_forest"
        self.brush_radius = 3
        self.brush_amount = 0.05

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        if delta > 0:
            self._scale *= 1.15
        else:
            self._scale /= 1.15
        self._scale = _clamp(self._scale, 0.3, 20.0)
        self.resetTransform()
        self.scale(self._scale, self._scale)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MiddleButton or (event.button() == Qt.LeftButton and event.modifiers() & Qt.AltModifier):
            self._dragging = True
            self._last_pos = event.pos()
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()
            return

        if event.button() == Qt.LeftButton:
            x,y = self._map_to_cell(event.pos())
            self.clicked.emit(x,y)
            # begin paint if in edit modes
            if self.edit_mode in ("raise","lower","paint_biome"):
                self._apply_brush(x,y)
            event.accept()
            return

        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if self._dragging and (event.button() == Qt.MiddleButton or event.button() == Qt.LeftButton):
            self._dragging = False
            self._last_pos = None
            self.setCursor(Qt.ArrowCursor)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._dragging and self._last_pos is not None:
            delta = event.pos() - self._last_pos
            self._last_pos = event.pos()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            event.accept()
            return

        x,y = self._map_to_cell(event.pos())
        self.hovered.emit(x,y)
        if event.buttons() & Qt.LeftButton and self.edit_mode in ("raise","lower","paint_biome"):
            self._apply_brush(x,y)
        super().mouseMoveEvent(event)

    def _apply_brush(self, x:int, y:int):
        if self.edit_mode == "paint_biome":
            self.painted.emit(x,y,"paint_biome", 0.0)
        elif self.edit_mode == "raise":
            self.painted.emit(x,y,"raise", +self.brush_amount)
        elif self.edit_mode == "lower":
            self.painted.emit(x,y,"lower", -self.brush_amount)

    def _map_to_cell(self, pos) -> Tuple[int,int]:
        # map scene coordinates to cell coordinates (assuming pixmap at 0,0)
        sp = self.mapToScene(pos)
        x = int(sp.x())
        y = int(sp.y())
        if x < 0: x = 0
        if y < 0: y = 0
        return x,y


class PlanetMapWindow(QMainWindow):
    def __init__(self, widget: "PlanetGenWidget"):
        super().__init__()
        self.widget = widget
        self.setWindowTitle("Planet Map — Campaign Forge")
        self.resize(1200, 720)

        self.scene = QGraphicsScene(self)
        self.view = PlanetMapView(self)
        self.view.setScene(self.scene)
        self.pix_item = QGraphicsPixmapItem()
        self.scene.addItem(self.pix_item)
        self.setCentralWidget(self.view)

        self.status = QStatusBar(self)
        self.setStatusBar(self.status)

        self._build_dock()
        self._bind()

        self._regen_timer = QTimer(self)
        self._regen_timer.setSingleShot(True)
        self._regen_timer.timeout.connect(self._apply_pending_edits)

        self.pending_edits: List[Tuple[int,int,str,float]] = []

        self.refresh_image()

    def _build_dock(self):
        dock = QDockWidget("Layers & Tools", self)
        dock.setObjectName("PlanetGenLayersDock")
        dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)

        root = QWidget()
        v = QVBoxLayout(root)

        # base layer
        self.cmb_base = QComboBox()
        self.cmb_base.addItems(["Biomes","Elevation","Moisture","Temperature","Plates","Factions"])
        v.addWidget(QLabel("Base Layer"))
        v.addWidget(self.cmb_base)

        # overlays
        self.chk_rivers = QCheckBox("Rivers")
        self.chk_rivers.setChecked(True)
        self.chk_settlements = QCheckBox("Settlements")
        self.chk_settlements.setChecked(True)
        self.chk_roads = QCheckBox("Roads")
        self.chk_roads.setChecked(True)
        self.chk_pois = QCheckBox("POIs")
        self.chk_pois.setChecked(True)

        v.addWidget(QLabel("Overlays"))
        for c in (self.chk_rivers,self.chk_settlements,self.chk_roads,self.chk_pois):
            v.addWidget(c)

        v.addWidget(self._hline())

        # edit tools
        v.addWidget(QLabel("Edit Mode (beta)"))
        self.cmb_edit = QComboBox()
        self.cmb_edit.addItems(["Inspect","Raise Terrain","Lower Terrain","Paint Biome","Place POI"])
        v.addWidget(self.cmb_edit)

        self.cmb_biome = QComboBox()
        self.cmb_biome.addItem("temperate_forest")
        self.cmb_biome.addItem("grassland")
        self.cmb_biome.addItem("desert")
        self.cmb_biome.addItem("swamp")
        self.cmb_biome.addItem("tundra")
        self.cmb_biome.addItem("taiga")
        self.cmb_biome.addItem("mountain")
        self.cmb_biome.addItem("badlands")
        self.cmb_biome.addItem("wasteland")
        v.addWidget(QLabel("Biome Brush"))
        v.addWidget(self.cmb_biome)

        self.sp_brush = QSpinBox()
        self.sp_brush.setRange(1, 20)
        self.sp_brush.setValue(3)
        v.addWidget(QLabel("Brush Radius"))
        v.addWidget(self.sp_brush)

        self.sp_amount = QDoubleSpinBox()
        self.sp_amount.setRange(0.01, 0.50)
        self.sp_amount.setSingleStep(0.01)
        self.sp_amount.setValue(0.05)
        v.addWidget(QLabel("Raise/Lower Amount"))
        v.addWidget(self.sp_amount)

        self.btn_clear_edits = QPushButton("Clear Edits (regenerate)")
        v.addWidget(self.btn_clear_edits)

        v.addStretch(1)
        dock.setWidget(root)
        self.addDockWidget(Qt.RightDockWidgetArea, dock)

    def _hline(self):
        fr = QFrame()
        fr.setFrameShape(QFrame.HLine)
        fr.setFrameShadow(QFrame.Sunken)
        return fr

    def _bind(self):
        for w in (self.cmb_base, self.chk_rivers, self.chk_settlements, self.chk_roads, self.chk_pois):
            if isinstance(w, QComboBox):
                w.currentIndexChanged.connect(self.refresh_image)
            else:
                w.stateChanged.connect(self.refresh_image)

        self.view.hovered.connect(self._on_hover)
        self.view.clicked.connect(self._on_click)
        self.view.painted.connect(self._on_paint)

        self.cmb_edit.currentIndexChanged.connect(self._on_edit_mode)
        self.cmb_biome.currentIndexChanged.connect(self._sync_brush)
        self.sp_brush.valueChanged.connect(self._sync_brush)
        self.sp_amount.valueChanged.connect(self._sync_brush)
        self.btn_clear_edits.clicked.connect(self._clear_edits)

        self._on_edit_mode()
        self._sync_brush()

    def _on_edit_mode(self):
        idx = self.cmb_edit.currentIndex()
        mode = "inspect"
        if idx == 1: mode = "raise"
        elif idx == 2: mode = "lower"
        elif idx == 3: mode = "paint_biome"
        elif idx == 4: mode = "place_poi"
        self.view.edit_mode = mode

    def _sync_brush(self):
        self.view.paint_biome_id = self.cmb_biome.currentText().strip()
        self.view.brush_radius = int(self.sp_brush.value())
        self.view.brush_amount = float(self.sp_amount.value())

    def _on_hover(self, x:int, y:int):
        w = self.widget.world
        if not w:
            return
        if x >= w.cfg.width or y >= w.cfg.height:
            return
        info = self.widget.cell_info(x,y)
        self.status.showMessage(info)

    def _on_click(self, x:int, y:int):
        w = self.widget.world
        if not w:
            return
        if x >= w.cfg.width or y >= w.cfg.height:
            return
        if self.view.edit_mode == "place_poi":
            # quick add POI
            name = f"Custom POI ({x},{y})"
            self.widget.add_custom_poi(x,y,name)
            self.refresh_image()
            return

    def _on_paint(self, x:int, y:int, mode: str, amt: float):
        # stash edits and debounce regeneration
        self.pending_edits.append((x,y,mode,amt))
        self._regen_timer.start(120)

    def _apply_pending_edits(self):
        if not self.pending_edits:
            return
        # apply to overrides through widget
        for x,y,mode,amt in self.pending_edits:
            self.widget.apply_brush_edit(x,y,mode,amt, self.view.brush_radius, self.view.paint_biome_id)
        self.pending_edits.clear()
        self.widget.regenerate_world()
        self.refresh_image()

    def _clear_edits(self):
        self.widget.clear_overrides()
        self.widget.regenerate_world()
        self.refresh_image()

    def refresh_image(self):
        img = self.widget.render_composite(
            base_layer=self.cmb_base.currentText(),
            show_rivers=self.chk_rivers.isChecked(),
            show_settlements=self.chk_settlements.isChecked(),
            show_roads=self.chk_roads.isChecked(),
            show_pois=self.chk_pois.isChecked(),
        )
        self.pix_item.setPixmap(QPixmap.fromImage(img))
        self.scene.setSceneRect(QRectF(0,0,img.width(), img.height()))


class PlanetGenWidget(QWidget):
    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx
        self.plugin_id = "planetgen"
        self.tables_dir = Path(__file__).resolve().parent / "tables"

        self.tables_biomes = _load_json(self.tables_dir / "biomes.json")
        self.tables_presets = _load_json(self.tables_dir / "presets.json")
        self.tables_factions = _load_json(self.tables_dir / "factions.json")

        self.world: Optional[PlanetWorld] = None
        self.map_window: Optional[PlanetMapWindow] = None

        # sparse overrides (persisted)
        self.overrides: Dict[str, Any] = {
            "elevation_delta": {},   # "x,y": float
            "biome_override": {},    # "x,y": "biome_id"
            "poi_edits": [],         # list of custom POIs
        }

        self._build_ui()

        # Start blank: generation is user-triggered (keeps app startup fast)
        self._update_enabled()
        self.txt_log.append("Ready. Click \"Generate Planet\" to create a world.")
# ---------- UI ----------
    def _build_ui(self):
        root = QVBoxLayout(self)

        header = QLabel("<b>Planet Generator</b> — terrain, climate, biomes, factions, settlements, POIs, exports.")
        header.setWordWrap(True)
        root.addWidget(header)

        box = QGroupBox("Generation Settings")
        form = QFormLayout(box)

        self.cmb_preset = QComboBox()
        for k,v in self.tables_presets["presets"].items():
            self.cmb_preset.addItem(f"{v['name']} [{k}]", k)
        form.addRow("World Type", self.cmb_preset)

        self.sp_w = QSpinBox(); self.sp_w.setRange(128, 2048); self.sp_w.setValue(512)
        self.sp_h = QSpinBox(); self.sp_h.setRange(64, 1024); self.sp_h.setValue(256)
        wh = QWidget(); hbox = QHBoxLayout(wh); hbox.setContentsMargins(0,0,0,0)
        hbox.addWidget(QLabel("W")); hbox.addWidget(self.sp_w)
        hbox.addWidget(QLabel("H")); hbox.addWidget(self.sp_h)
        form.addRow("Map Size", wh)

        self.sp_ocean = QDoubleSpinBox(); self.sp_ocean.setRange(0.05, 0.95); self.sp_ocean.setSingleStep(0.01); self.sp_ocean.setValue(0.70)
        form.addRow("Ocean %", self.sp_ocean)

        self.sp_plates = QSpinBox(); self.sp_plates.setRange(4, 40); self.sp_plates.setValue(18)
        form.addRow("Plate Count", self.sp_plates)

        self.sp_rivers = QSpinBox(); self.sp_rivers.setRange(0, 800); self.sp_rivers.setValue(220)
        form.addRow("River Count", self.sp_rivers)

        self.sp_factions = QSpinBox(); self.sp_factions.setRange(0, 20); self.sp_factions.setValue(9)
        form.addRow("Faction Count", self.sp_factions)

        self.sp_settlements = QSpinBox(); self.sp_settlements.setRange(0, 250); self.sp_settlements.setValue(60)
        form.addRow("Settlement Count", self.sp_settlements)

        self.sp_rugged = QDoubleSpinBox(); self.sp_rugged.setRange(0.2, 2.5); self.sp_rugged.setSingleStep(0.1); self.sp_rugged.setValue(1.0)
        form.addRow("Ruggedness", self.sp_rugged)

        self.sp_coast = QSpinBox(); self.sp_coast.setRange(0, 12); self.sp_coast.setValue(3)
        form.addRow("Coast Smooth Iters", self.sp_coast)

        self.sp_tempbias = QDoubleSpinBox(); self.sp_tempbias.setRange(-0.30, 0.30); self.sp_tempbias.setSingleStep(0.02); self.sp_tempbias.setValue(0.0)
        form.addRow("Temperature Bias", self.sp_tempbias)

        self.sp_rainbias = QDoubleSpinBox(); self.sp_rainbias.setRange(-0.30, 0.30); self.sp_rainbias.setSingleStep(0.02); self.sp_rainbias.setValue(0.0)
        form.addRow("Rainfall Bias", self.sp_rainbias)

        self.chk_use_project_seed = QCheckBox("Use Project Master Seed")
        self.chk_use_project_seed.setChecked(True)
        form.addRow("", self.chk_use_project_seed)

        self.sp_seed = QSpinBox()
        self.sp_seed.setRange(0, 2**31-1)
        self.sp_seed.setValue(1337)
        form.addRow("Seed (if not project)", self.sp_seed)

        root.addWidget(box)

        btns = QHBoxLayout()
        self.btn_generate = QPushButton("Generate Planet")
        self.btn_map = QPushButton("Open Map Window")
        self.btn_export = QPushButton("Export Session Pack")
        self.btn_scratch = QPushButton("Send Summary to Scratchpad")
        btns.addWidget(self.btn_generate)
        btns.addWidget(self.btn_map)
        btns.addWidget(self.btn_export)
        btns.addWidget(self.btn_scratch)
        root.addLayout(btns)

        self.txt_log = QTextEdit()
        self.txt_log.setReadOnly(True)
        self.txt_log.setPlaceholderText("Planet Generator log…")
        root.addWidget(self.txt_log, 1)

        # bindings
        self.btn_generate.clicked.connect(self._on_generate)
        self.btn_map.clicked.connect(self._on_open_map)
        self.btn_export.clicked.connect(self._on_export)
        self.btn_scratch.clicked.connect(self._on_scratchpad)

    def _log(self, msg: str):
        try:
            self.ctx.log(f"[PlanetGen] {msg}")
        except Exception:
            pass
        self.txt_log.append(msg)

    def _update_enabled(self):
        has_world = self.world is not None
        self.btn_map.setEnabled(has_world)
        self.btn_export.setEnabled(has_world)
        self.btn_scratch.setEnabled(has_world)

    # ---------- State ----------
    def serialize_state(self) -> dict:
        cfg = self._build_cfg()
        return {
            "version": 1,
            "cfg": asdict(cfg),
            "overrides": self.overrides,
        }

    def load_state(self, state: dict) -> None:
        if not state:
            return
        try:
            cfg = state.get("cfg", {})
            # apply to UI
            preset_key = cfg.get("preset_key", "fantasy")
            # find index
            for i in range(self.cmb_preset.count()):
                if self.cmb_preset.itemData(i) == preset_key:
                    self.cmb_preset.setCurrentIndex(i)
                    break
            self.sp_w.setValue(int(cfg.get("width", 512)))
            self.sp_h.setValue(int(cfg.get("height", 256)))
            self.sp_ocean.setValue(float(cfg.get("ocean_percent", 0.70)))
            self.sp_plates.setValue(int(cfg.get("plate_count", 18)))
            self.sp_rivers.setValue(int(cfg.get("river_count", 220)))
            self.sp_factions.setValue(int(cfg.get("faction_count", 9)))
            self.sp_settlements.setValue(int(cfg.get("settlement_count", 60)))
            self.sp_rugged.setValue(float(cfg.get("ruggedness", 1.0)))
            self.sp_tempbias.setValue(float(cfg.get("temperature_bias", 0.0)))
            self.sp_rainbias.setValue(float(cfg.get("rainfall_bias", 0.0)))
            self.sp_seed.setValue(int(cfg.get("master_seed", 1337)))
            self.overrides = state.get("overrides", self.overrides) or self.overrides
        except Exception as e:
            self._log(f"Failed to load state: {e}")

    # ---------- Generation ----------
    def _build_cfg(self) -> PlanetGenConfig:
        preset_key = self.cmb_preset.currentData() or "fantasy"
        seed = int(self.ctx.master_seed) if self.chk_use_project_seed.isChecked() else int(self.sp_seed.value())
        return PlanetGenConfig(
            preset_key=str(preset_key),
            width=int(self.sp_w.value()),
            height=int(self.sp_h.value()),
            master_seed=int(seed),
            ocean_percent=float(self.sp_ocean.value()),
            plate_count=int(self.sp_plates.value()),
            river_count=int(self.sp_rivers.value()),
            faction_count=int(self.sp_factions.value()),
            settlement_count=int(self.sp_settlements.value()),
            ruggedness=float(self.sp_rugged.value()),
            temperature_bias=float(self.sp_tempbias.value()),
            rainfall_bias=float(self.sp_rainbias.value()),
            coast_smooth_iters=int(self.sp_coast.value()),
        )

    def regenerate_world(self):
        cfg = self._build_cfg()
        t0 = time.time()
        try:
            self.world = generate_world(cfg, self.tables_dir, overrides=self.overrides)
            dt = time.time() - t0
            self._log(f"Generated {cfg.preset_key} world: {cfg.width}x{cfg.height} in {dt:.2f}s (seed={cfg.master_seed}).")
            self._update_enabled()
        except Exception as e:
            self.world = None
            self._update_enabled()
            self._log(f"Generation failed: {e}")

    def _on_generate(self):
        self.regenerate_world()
        if self.map_window:
            self.map_window.refresh_image()

    # ---------- Map window ----------
    def _on_open_map(self):
        if not self.world:
            QMessageBox.warning(self, "Planet Generator", "No world generated yet.")
            return
        if not self.map_window:
            self.map_window = PlanetMapWindow(self)
        self.map_window.show()
        self.map_window.raise_()
        self.map_window.activateWindow()

    # ---------- Edits ----------
    def clear_overrides(self):
        self.overrides = {"elevation_delta": {}, "biome_override": {}, "poi_edits": []}

    def _cell_key(self, x:int, y:int) -> str:
        return f"{x},{y}"

    def apply_brush_edit(self, x:int, y:int, mode:str, amt:float, radius:int, biome_id:str):
        if not self.world:
            return
        w,h = self.world.cfg.width, self.world.cfg.height
        for oy in range(-radius, radius+1):
            for ox in range(-radius, radius+1):
                if ox*ox + oy*oy > radius*radius:
                    continue
                nx = (x + ox) % w
                ny = y + oy
                if ny < 0 or ny >= h:
                    continue
                key = self._cell_key(nx,ny)
                if mode in ("raise","lower"):
                    d = self.overrides["elevation_delta"].get(key, 0.0)
                    self.overrides["elevation_delta"][key] = float(d) + float(amt)
                elif mode == "paint_biome":
                    self.overrides["biome_override"][key] = str(biome_id)

    def add_custom_poi(self, x:int, y:int, name:str):
        self.overrides.setdefault("poi_edits", []).append({"x":x,"y":y,"name":name,"category":"custom","notes":""})
        self._log(f"Added custom POI at ({x},{y}).")

    # ---------- Info ----------
    def cell_info(self, x:int, y:int) -> str:
        w = self.world
        if not w:
            return ""
        if x >= w.cfg.width or y >= w.cfg.height:
            return ""
        i = y*w.cfg.width + x
        elev = w.elevation[i]
        bio = w.biome[i]
        t = w.temperature[i]
        m = w.moisture[i]
        oc = w.ocean[i]
        fid = w.faction_id[i]
        fs = w.faction_strength[i]
        rv = w.river[i]
        parts = [f"({x},{y})"]
        parts.append("OCEAN" if oc else "LAND")
        parts.append(f"elev={elev:+.2f}")
        parts.append(f"biome={bio}")
        parts.append(f"T={t:.2f} M={m:.2f}")
        if rv>0:
            parts.append(f"river={rv}")
        if fid >= 0:
            parts.append(f"faction={fid} ({fs:.2f})")
        return " | ".join(parts)

    # ---------- Rendering ----------
    def render_composite(self, base_layer: str, show_rivers: bool=True, show_settlements: bool=True, show_roads: bool=True, show_pois: bool=True) -> QImage:
        if not self.world:
            return QImage(1,1, QImage.Format_ARGB32)
        w = self.world.cfg.width
        h = self.world.cfg.height

        img = QImage(w, h, QImage.Format_ARGB32)
        img.fill(QColor(20,20,25))

        base_layer = (base_layer or "Biomes").strip().lower()
        if base_layer == "elevation":
            self._render_elevation(img)
        elif base_layer == "moisture":
            self._render_scalar(img, self.world.moisture)
        elif base_layer == "temperature":
            self._render_scalar(img, self.world.temperature)
        elif base_layer == "plates":
            self._render_plates(img)
        elif base_layer == "factions":
            self._render_factions(img)
        else:
            self._render_biomes(img)

        painter = QPainter(img)
        painter.setRenderHint(QPainter.Antialiasing, True)

        if show_roads:
            self._draw_roads(painter)
        if show_rivers:
            self._draw_rivers(painter)
        if show_settlements:
            self._draw_settlements(painter)
        if show_pois:
            self._draw_pois(painter)

        painter.end()
        return img

    def _render_biomes(self, img: QImage):
        biome_map = {b["id"]: b for b in self.tables_biomes["biomes"]}
        w = self.world.cfg.width
        h = self.world.cfg.height
        for y in range(h):
            for x in range(w):
                i = y*w+x
                bid = self.world.biome[i]
                b = biome_map.get(bid) or biome_map.get("wasteland") or {"color":[120,120,120]}
                img.setPixelColor(x,y, _rgb(b["color"]))

    def _render_scalar(self, img: QImage, arr: List[float]):
        w = self.world.cfg.width
        h = self.world.cfg.height
        for y in range(h):
            for x in range(w):
                v = _clamp(arr[y*w+x], 0.0, 1.0)
                c = int(v*255)
                img.setPixelColor(x,y, QColor(c,c,c))

    def _render_elevation(self, img: QImage):
        w = self.world.cfg.width
        h = self.world.cfg.height
        # normalize elevation for display
        e = self.world.elevation
        mn = min(e); mx = max(e)
        rng = (mx-mn) if mx>mn else 1.0
        for y in range(h):
            for x in range(w):
                i=y*w+x
                v = (e[i]-mn)/rng
                # ocean darker
                if self.world.ocean[i]:
                    v *= 0.6
                c = int(_clamp(v,0,1)*255)
                img.setPixelColor(x,y, QColor(c,c,c))

    def _render_plates(self, img: QImage):
        w = self.world.cfg.width
        h = self.world.cfg.height
        # deterministic plate colors
        for y in range(h):
            for x in range(w):
                i=y*w+x
                pid = int(self.world.plates[i])
                r = (pid*53) % 255
                g = (pid*97) % 255
                b = (pid*193) % 255
                img.setPixelColor(x,y, QColor(r,g,b))

    def _render_factions(self, img: QImage):
        w = self.world.cfg.width
        h = self.world.cfg.height
        for y in range(h):
            for x in range(w):
                i=y*w+x
                if self.world.ocean[i]:
                    img.setPixelColor(x,y, QColor(20,60,130))
                    continue
                fid = self.world.faction_id[i]
                if fid < 0:
                    img.setPixelColor(x,y, QColor(110,110,110))
                    continue
                col = self._faction_color(fid)
                s = _clamp(self.world.faction_strength[i], 0.0, 1.0)
                # blend toward neutral with low strength
                r = int(_lerp(120, col.red(), s))
                g = int(_lerp(120, col.green(), s))
                b = int(_lerp(120, col.blue(), s))
                img.setPixelColor(x,y, QColor(r,g,b))

    def _faction_color(self, fid:int) -> QColor:
        # stable vivid-ish colors
        r = (fid*83 + 50) % 200 + 30
        g = (fid*131 + 90) % 200 + 30
        b = (fid*197 + 120) % 200 + 30
        return QColor(r,g,b)

    def _draw_rivers(self, p: QPainter):
        w = self.world.cfg.width
        h = self.world.cfg.height
        pen = QPen(QColor(40,140,235, 210))
        pen.setWidthF(1.0)
        p.setPen(pen)
        for y in range(h):
            for x in range(w):
                i=y*w+x
                rv = self.world.river[i]
                if rv > 0 and not self.world.ocean[i]:
                    a = int(_clamp(rv/255.0, 0, 1) * 180) + 30
                    p.setPen(QPen(QColor(40,140,235, a), 1))
                    p.drawPoint(x,y)

    def _draw_settlements(self, p: QPainter):
        for s in self.world.settlements:
            x,y = int(s["x"]), int(s["y"])
            kind = s.get("kind","town")
            fid = s.get("faction",-1)
            col = self._faction_color(fid) if isinstance(fid,int) and fid>=0 else QColor(240,240,240)
            if kind == "capital":
                p.setBrush(QBrush(col))
                p.setPen(QPen(QColor(0,0,0,200), 1))
                p.drawEllipse(QPointF(x,y), 4, 4)
            elif kind == "city":
                p.setBrush(QBrush(col))
                p.setPen(QPen(QColor(0,0,0,200), 1))
                p.drawEllipse(QPointF(x,y), 3, 3)
            else:
                p.setBrush(QBrush(col))
                p.setPen(QPen(QColor(0,0,0,180), 1))
                p.drawEllipse(QPointF(x,y), 2, 2)

    def _draw_roads(self, p: QPainter):
        pen = QPen(QColor(180,160,90, 160))
        pen.setWidthF(1.0)
        p.setPen(pen)
        for poly in self.world.roads:
            if len(poly) < 2:
                continue
            for (x0,y0),(x1,y1) in zip(poly, poly[1:]):
                p.drawLine(x0,y0,x1,y1)

    def _draw_pois(self, p: QPainter):
        # simple glyphs by category
        for poi in self.world.pois:
            x,y = int(poi["x"]), int(poi["y"])
            cat = poi.get("category","")
            if cat == "natural":
                col = QColor(240,240,240, 200)
                p.setPen(QPen(col, 1))
                p.drawRect(x-1,y-1,3,3)
            elif cat == "civilization":
                col = QColor(255,210,80, 220)
                p.setPen(QPen(col, 1))
                p.drawEllipse(QPointF(x,y), 2, 2)
            elif cat == "catastrophe":
                col = QColor(255,80,80, 230)
                p.setPen(QPen(col, 1))
                p.drawLine(x-2,y-2,x+2,y+2)
                p.drawLine(x-2,y+2,x+2,y-2)
            else:
                col = QColor(160,220,255, 220)
                p.setPen(QPen(col, 1))
                p.drawPoint(x,y)

    # ---------- Export ----------
    def _on_export(self):
        if not self.world:
            QMessageBox.warning(self, "Planet Generator", "No world to export.")
            return
        try:
            pack = self.ctx.export_manager.create_session_pack("planet", seed=self.world.cfg.master_seed)
            # images
            base = self.render_composite("Biomes", True, True, True, True)
            elev = self.render_composite("Elevation", False, False, False, False)
            factions = self.render_composite("Factions", True, True, False, True)
            save_png(base, pack / "world_map.png")
            save_png(elev, pack / "elevation.png")
            save_png(factions, pack / "factions.png")
            # atlas
            atlas_payload = self.build_atlas_payload()
            md = build_atlas_markdown(atlas_payload)
            (pack / "atlas.md").write_text(md, encoding="utf-8")
            save_json(atlas_payload, pack / "atlas.json")
            self._log(f"Exported session pack: {pack}")
        except Exception as e:
            QMessageBox.critical(self, "Planet Generator", f"Export failed:\n{e}")

    # ---------- Scratchpad ----------
    def _on_scratchpad(self):
        if not self.world:
            return
        payload = self.build_atlas_payload()
        md = build_atlas_markdown(payload)
        try:
            self.ctx.scratchpad_add(md, tags=["World","Planet","PlanetGen", f"WorldType:{self.world.cfg.preset_key}"])
            self._log("Sent atlas summary to Scratchpad.")
        except Exception as e:
            self._log(f"Failed to send to Scratchpad: {e}")

    def build_atlas_payload(self) -> Dict[str, Any]:
        w = self.world
        preset_key = w.cfg.preset_key
        preset = self.tables_presets["presets"].get(preset_key, {})
        # factions flavored via archetypes table
        arche = self.tables_factions["archetypes"].get(preset.get("faction_style","feudal"), [])
        factions = []
        for fid in range(max(0, min(20, w.cfg.faction_count))):
            a = arche[fid % len(arche)] if arche else {"name": f"Faction {fid}", "tags": [], "motives": []}
            factions.append({
                "id": fid,
                "name": a.get("name", f"Faction {fid}"),
                "style": preset.get("faction_style",""),
                "tags": a.get("tags", []),
                "motives": a.get("motives", []),
                "core_hint": "Generated core region (see faction map layer).",
            })
        # settlements named deterministically
        settlements = []
        for i,s in enumerate(w.settlements):
            settlements.append({
                "name": self._settlement_name(i, s.get("kind","town")),
                "kind": s.get("kind","town"),
                "x": s.get("x"), "y": s.get("y"),
                "faction": s.get("faction"),
            })
        pois = [{"name":p.get("name"),"category":p.get("category"),"x":p.get("x"),"y":p.get("y"),"biome":p.get("biome")} for p in w.pois[:400]]

        return {
            "title": f"{preset.get('name','World')} (seed {w.cfg.master_seed})",
            "params": {
                "preset": preset_key,
                "size": f"{w.cfg.width}x{w.cfg.height}",
                "ocean_percent": w.cfg.ocean_percent,
                "plate_count": w.cfg.plate_count,
                "river_count": w.cfg.river_count,
                "faction_count": w.cfg.faction_count,
                "settlement_count": w.cfg.settlement_count,
                "ruggedness": w.cfg.ruggedness,
                "temp_bias": w.cfg.temperature_bias,
                "rain_bias": w.cfg.rainfall_bias,
            },
            "factions": factions,
            "settlements": settlements,
            "pois": pois,
        }

    def _settlement_name(self, i:int, kind:str) -> str:
        # deterministic pseudo-name: syllables
        seed = (self.world.cfg.master_seed + 91000 + i*97) & 0xFFFFFFFF
        syll1 = ["Al","Bel","Cor","Dor","Eld","Fen","Gal","Har","Ith","Jar","Kel","Lor","Mor","Nor","Or","Pel","Quel","Rav","Sor","Tor","Ul","Val","Wen","Yor","Zan"]
        syll2 = ["a","e","i","o","u","ae","ia","oa","uu","ei"]
        syll3 = ["ford","haven","gate","watch","dale","shire","crest","port","hold","field","wick","marsh","fall","reach","spire","barrow","cross","mead","brook","cairn"]
        def r(n): 
            return (seed >> (n*7)) & 0xFFFFFFFF
        a = syll1[r(1) % len(syll1)]
        b = syll2[r(2) % len(syll2)]
        c = syll3[r(3) % len(syll3)]
        if kind == "capital":
            return f"{a}{b}{c} Prime"
        if kind == "city":
            return f"{a}{b}{c}"
        return f"{a}{b}{c}"

# local helper
def _lerp(a: float, b: float, t: float) -> float:
    return a + (b-a)*t
