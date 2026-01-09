from __future__ import annotations
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any

from PySide6.QtCore import Qt, Signal, QPoint, QByteArray
from PySide6.QtGui import QAction, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSpinBox, QDoubleSpinBox, QCheckBox, QGroupBox, QFormLayout,
    QGraphicsView, QFileDialog, QMessageBox, QApplication, QTextEdit,
    QComboBox, QLineEdit, QMainWindow, QScrollArea
)

from .generator import (
    HexMapConfig, ThemePack, HexCell, Coord,
    generate_hex_cells, generate_rivers_and_roads,
    generate_settlements, generate_road_network,
    build_key, build_poi_list, load_theme_packs, save_theme_pack,
    generate_hex_content
)
from .renderer import (
    RenderConfig, build_scene, scene_to_image, can_export_svg, scene_to_svg
)


class ClickableGraphicsView(QGraphicsView):
    """
    View used in the preview window. Emits hexClicked(q,r) on left click.
    """
    hexClicked = Signal(int, int)  # q, r

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.scene():
            item = self.itemAt(event.pos())
            if item is not None and hasattr(item, "q") and hasattr(item, "r"):
                self.hexClicked.emit(int(item.q), int(item.r))
        super().mousePressEvent(event)

    def wheelEvent(self, event):
        # Zoom with wheel
        zoom_in = 1.15
        zoom_out = 1 / zoom_in
        if event.angleDelta().y() > 0:
            self.scale(zoom_in, zoom_in)
        else:
            self.scale(zoom_out, zoom_out)


class HexMapPreviewWindow(QMainWindow):
    closed = Signal()

    def __init__(self, title: str = "Hex Map Preview"):
        super().__init__()
        self.setWindowTitle(title)
        self.view = ClickableGraphicsView()
        self.view.setDragMode(QGraphicsView.ScrollHandDrag)
        self.view.setViewportUpdateMode(QGraphicsView.BoundingRectViewportUpdate)
        self.setCentralWidget(self.view)

    def set_scene(self, scene):
        self.view.setScene(scene)
        if scene:
            try:
                self.view.fitInView(scene.sceneRect(), Qt.KeepAspectRatio)
            except Exception:
                pass

    def closeEvent(self, event):
        try:
            self.closed.emit()
        except Exception:
            pass
        super().closeEvent(event)


class HexMapWidget(QWidget):
    """
    Hex Map generator module.

    New features:
    - detachable preview window
    - paint/edit terrain + undo
    - per-hex content cards
    - settlements + road network
    - session pack export incl. gazetteer markdown
    """
    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx

        self._cells: Dict[Coord, HexCell] = {}
        self._scene = None
        self._rivers: List[List[Coord]] = []
        self._roads: List[List[Coord]] = []

        # per-hex content cards + lock flags
        self._hex_cards: Dict[str, Dict[str, Any]] = {}  # "q,r" -> {"locked": bool, "card": {...}}
        self._selected: Optional[Coord] = None

        # undo stack for terrain painting
        self._undo_stack: List[Dict[str, Any]] = []

        # Preview window
        self._preview_win: Optional[HexMapPreviewWindow] = None

        # Theme packs
        self._theme_packs = load_theme_packs(self.ctx.project_dir)
        self._current_theme = self._theme_packs.get("OSR")

        self._build_ui()
        self._wire_signals()
        self._refresh_terrain_lists()

        # keyboard shortcut
        QShortcut(QKeySequence.Undo, self, activated=self.on_undo)

    # ---------- UI ----------

    def _build_ui(self):
        # Controls
        self.theme_combo = QComboBox()
        self._refresh_theme_combo()
        self.btn_save_theme = QPushButton("Save Theme Pack…")

        self.w_spin = QSpinBox(); self.w_spin.setRange(3, 200); self.w_spin.setValue(25)
        self.h_spin = QSpinBox(); self.h_spin.setRange(3, 200); self.h_spin.setValue(18)
        self.seed_spin = QSpinBox(); self.seed_spin.setRange(0, 2_147_483_647); self.seed_spin.setValue(1337)
        self.poi_spin = QDoubleSpinBox(); self.poi_spin.setRange(0.0, 1.0); self.poi_spin.setSingleStep(0.01); self.poi_spin.setValue(0.08)

        self.hex_size = QSpinBox(); self.hex_size.setRange(10, 90); self.hex_size.setValue(22)

        self.show_grid = QCheckBox("Grid"); self.show_grid.setChecked(True)
        self.show_labels = QCheckBox("Labels"); self.show_labels.setChecked(True)
        self.show_poi = QCheckBox("POI markers"); self.show_poi.setChecked(True)

        self.rivers_enabled = QCheckBox("Rivers"); self.rivers_enabled.setChecked(False)
        self.river_count = QSpinBox(); self.river_count.setRange(0, 20); self.river_count.setValue(1)

        self.settlements_enabled = QCheckBox("Settlements"); self.settlements_enabled.setChecked(True)
        self.settlement_count = QSpinBox(); self.settlement_count.setRange(0, 80); self.settlement_count.setValue(8)

        self.roads_enabled = QCheckBox("Roads"); self.roads_enabled.setChecked(True)
        self.road_count = QSpinBox(); self.road_count.setRange(0, 30); self.road_count.setValue(0)  # extra connections

        self.btn_generate = QPushButton("Generate")
        self.btn_open_preview = QPushButton("Open Map Preview Window")

        self.btn_export_png = QPushButton("Export PNG…")
        self.btn_export_svg = QPushButton("Export SVG…")
        self.btn_export_md = QPushButton("Export Key Markdown…")
        self.btn_export_pack = QPushButton("Export Session Pack (Map + Gazetteer)")

        self.btn_send_scratch = QPushButton("Send Key to Scratchpad")
        self.btn_copy_md = QPushButton("Copy Key Markdown")

        # Painter
        self.paint_mode = QCheckBox("Paint Terrain"); self.paint_mode.setChecked(False)
        self.paint_combo = QComboBox()
        self.btn_undo = QPushButton("Undo Paint")

        # Selected hex editor (existing)
        self.editor_box = QGroupBox("Selected Hex")
        ed = QFormLayout(self.editor_box)
        self.sel_label = QLabel("—")
        self.terrain_combo = QComboBox()
        self.poi_edit = QLineEdit()
        self.btn_apply_hex = QPushButton("Apply")
        self.btn_clear_poi = QPushButton("Clear POI")

        row_btns = QHBoxLayout()
        row_btns.addWidget(self.btn_apply_hex)
        row_btns.addWidget(self.btn_clear_poi)
        ed.addRow("Hex:", self.sel_label)
        ed.addRow("Terrain:", self.terrain_combo)
        ed.addRow("POI:", self.poi_edit)
        ed.addRow("", QWidget())
        ed.addRow(row_btns)

        # Key preview
        self.key_preview = QTextEdit()
        self.key_preview.setReadOnly(True)
        self.key_preview.setPlaceholderText("Key + POIs will appear here after generation...")

        # Content card pane
        self.card_preview = QTextEdit()
        self.card_preview.setReadOnly(True)
        self.card_preview.setPlaceholderText("Select a hex in the preview window to see its content card...")

        self.btn_roll_card = QPushButton("Roll / Refresh Card")
        self.btn_lock_card = QPushButton("Lock Card")
        self.btn_send_card = QPushButton("Send Card to Scratchpad")

        # Layout
        # The controls can get tall on smaller screens, so we wrap the entire
        # module UI in a scroll area.
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll)

        content = QWidget()
        scroll.setWidget(content)

        root = QHBoxLayout(content)
        root.setContentsMargins(8, 8, 8, 8)

        left = QVBoxLayout()
        right = QVBoxLayout()

        # Theme box
        theme_box = QGroupBox("Biome / Theme")
        theme_form = QFormLayout(theme_box)
        theme_form.addRow("Theme:", self.theme_combo)
        theme_form.addRow("", self.btn_save_theme)

        # Generation box
        gen_box = QGroupBox("Generation")
        gen_form = QFormLayout(gen_box)
        gen_form.addRow("Width:", self.w_spin)
        gen_form.addRow("Height:", self.h_spin)
        gen_form.addRow("Seed:", self.seed_spin)
        gen_form.addRow("POI density:", self.poi_spin)

        # Render box
        render_box = QGroupBox("Render")
        render_form = QFormLayout(render_box)
        render_form.addRow("Hex size:", self.hex_size)

        row_tog = QHBoxLayout()
        row_tog.addWidget(self.show_grid)
        row_tog.addWidget(self.show_labels)
        row_tog.addWidget(self.show_poi)
        render_form.addRow("Show:", QWidget())
        render_form.addRow("", QWidget())
        render_form.addRow("", self._wrap(row_tog))

        # Rivers/roads/settlements box
        feat_box = QGroupBox("World Features")
        feat_form = QFormLayout(feat_box)
        row_riv = QHBoxLayout(); row_riv.addWidget(self.rivers_enabled); row_riv.addWidget(QLabel("Count:")); row_riv.addWidget(self.river_count)
        feat_form.addRow(self._wrap(row_riv))

        row_set = QHBoxLayout(); row_set.addWidget(self.settlements_enabled); row_set.addWidget(QLabel("Count:")); row_set.addWidget(self.settlement_count)
        feat_form.addRow(self._wrap(row_set))

        row_road = QHBoxLayout(); row_road.addWidget(self.roads_enabled); row_road.addWidget(QLabel("Extra:")); row_road.addWidget(self.road_count)
        feat_form.addRow(self._wrap(row_road))

        # Paint box
        paint_box = QGroupBox("Terrain Painting")
        paint_form = QFormLayout(paint_box)
        row_paint = QHBoxLayout()
        row_paint.addWidget(self.paint_mode)
        row_paint.addWidget(QLabel("Brush:"))
        row_paint.addWidget(self.paint_combo)
        paint_form.addRow(self._wrap(row_paint))
        row_undo = QHBoxLayout()
        row_undo.addWidget(self.btn_undo)
        paint_form.addRow(self._wrap(row_undo))

        # Buttons
        btns = QHBoxLayout()
        btns.addWidget(self.btn_generate)
        btns.addWidget(self.btn_open_preview)

        exports = QVBoxLayout()
        exports.addWidget(self.btn_export_pack)
        row_export = QHBoxLayout()
        row_export.addWidget(self.btn_export_png)
        row_export.addWidget(self.btn_export_svg)
        row_export.addWidget(self.btn_export_md)
        exports.addLayout(row_export)

        # Right side content card controls
        card_btns = QHBoxLayout()
        card_btns.addWidget(self.btn_roll_card)
        card_btns.addWidget(self.btn_lock_card)
        card_btns.addWidget(self.btn_send_card)

        left.addWidget(theme_box)
        left.addWidget(gen_box)
        left.addWidget(render_box)
        left.addWidget(feat_box)
        left.addWidget(paint_box)
        left.addLayout(btns)
        left.addLayout(exports)
        left.addWidget(self.btn_send_scratch)
        left.addWidget(self.btn_copy_md)
        left.addWidget(self.editor_box)

        right.addWidget(QLabel("Key / POIs Preview"))
        self.key_preview.setMinimumHeight(220)
        right.addWidget(self.key_preview, stretch=2)
        right.addWidget(QLabel("Per-Hex Content Card"))
        right.addLayout(card_btns)
        self.card_preview.setMinimumHeight(160)
        right.addWidget(self.card_preview, stretch=1)

        root.addLayout(left, stretch=0)
        root.addLayout(right, stretch=1)

    def _wrap(self, layout: QHBoxLayout) -> QWidget:
        w = QWidget()
        w.setLayout(layout)
        return w

    def _wire_signals(self):
        self.btn_generate.clicked.connect(self.on_generate)

        self.btn_open_preview.clicked.connect(self.on_open_preview)

        self.btn_export_png.clicked.connect(self.on_export_png)
        self.btn_export_svg.clicked.connect(self.on_export_svg)
        self.btn_export_md.clicked.connect(self.on_export_md)
        self.btn_export_pack.clicked.connect(self.on_export_session_pack)

        self.btn_send_scratch.clicked.connect(self.on_send_scratchpad)
        self.btn_copy_md.clicked.connect(self.on_copy_md)

        self.show_grid.toggled.connect(self.on_redraw)
        self.show_labels.toggled.connect(self.on_redraw)
        self.show_poi.toggled.connect(self.on_redraw)
        self.hex_size.valueChanged.connect(self.on_redraw)

        self.theme_combo.currentIndexChanged.connect(self.on_theme_changed)
        self.btn_save_theme.clicked.connect(self.on_save_theme)

        self.btn_apply_hex.clicked.connect(self.on_apply_hex)
        self.btn_clear_poi.clicked.connect(self.on_clear_poi)

        self.paint_mode.toggled.connect(self._sync_paint_ui)
        self.btn_undo.clicked.connect(self.on_undo)

        self.btn_roll_card.clicked.connect(self.on_roll_card)
        self.btn_lock_card.clicked.connect(self.on_toggle_lock_card)
        self.btn_send_card.clicked.connect(self.on_send_card_to_scratchpad)

    # ---------- Theme ----------

    def _refresh_theme_combo(self):
        self.theme_combo.clear()
        keys = sorted(self._theme_packs.keys())
        for k in keys:
            self.theme_combo.addItem(k)
        # pick OSR if present
        if "OSR" in keys:
            self.theme_combo.setCurrentIndex(keys.index("OSR"))

    def on_theme_changed(self, idx: int):
        key = self.theme_combo.currentText()
        self._current_theme = self._theme_packs.get(key)
        self._refresh_terrain_lists()

    def _refresh_terrain_lists(self):
        # populate terrain combo (editor + paint) based on theme weights
        self.terrain_combo.clear()
        self.paint_combo.clear()
        terrs = []
        if self._current_theme and self._current_theme.terrain_weights:
            terrs = list(self._current_theme.terrain_weights.keys())
        terrs = terrs or ["Plains", "Forest", "Hills", "Mountains", "Swamp", "Desert", "Water"]
        for t in terrs:
            self.terrain_combo.addItem(t)
            self.paint_combo.addItem(t)

    def on_save_theme(self):
        # Save the currently selected theme to project themes
        key = self.theme_combo.currentText()
        tp = self._theme_packs.get(key)
        if not tp:
            QMessageBox.warning(self, "No Theme", "No theme selected.")
            return

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Theme Pack JSON",
            str((self.ctx.project_dir / "themes" / f"{key}.json").resolve()),
            "Theme Pack (*.json)"
        )
        if not path:
            return
        try:
            save_theme_pack(Path(path), tp)
            self.ctx.log(f"[HexMap] Saved theme pack: {path}")
        except Exception as e:
            QMessageBox.warning(self, "Save Failed", f"Could not save theme pack:\n{e}")

    # ---------- Preview window ----------

    def _ensure_preview(self, show: bool = True):
        if self._preview_win is None:
            self._preview_win = HexMapPreviewWindow()
            self._preview_win.view.hexClicked.connect(self.on_hex_clicked)
            self._preview_win.closed.connect(self._on_preview_closed)
            if self._scene is not None:
                self._preview_win.set_scene(self._scene)
        if show:
            self._preview_win.show()
            self._preview_win.raise_()
            self._preview_win.activateWindow()

    def _on_preview_closed(self):
        self._preview_win = None

    def on_open_preview(self):
        self._ensure_preview(show=True)

    def _set_scene(self, scene):
        self._scene = scene
        if self._preview_win is not None:
            self._preview_win.set_scene(scene)

    # ---------- Generation / redraw ----------

    def _make_cfg(self) -> HexMapConfig:
        tp = self._current_theme
        if not tp:
            # fall back
            tp = ThemePack(name="Default", terrain_weights={"Plains": 1, "Forest": 1, "Hills": 1, "Mountains": 1}, poi_list=[])
        return HexMapConfig(
            width=int(self.w_spin.value()),
            height=int(self.h_spin.value()),
            seed=int(self.seed_spin.value()),
            poi_density=float(self.poi_spin.value()),
            terrain_weights=dict(tp.terrain_weights),
            poi_list=list(tp.poi_list),
            rivers_enabled=bool(self.rivers_enabled.isChecked()),
            river_count=int(self.river_count.value()),
            roads_enabled=bool(self.roads_enabled.isChecked()),
            road_count=int(self.road_count.value()),
        )

    def on_generate(self):
        cfg = self._make_cfg()
        self._refresh_terrain_lists()

        # generate cells
        self._cells = generate_hex_cells(cfg)

        # rivers (existing)
        import random as _random
        rng = _random.Random(cfg.seed)
        self._rivers, _roads_random = generate_rivers_and_roads(cfg, rng)

        # settlements + roads network
        settlements: List[Coord] = []
        if self.settlements_enabled.isChecked():
            settlements = generate_settlements(self._cells, cfg, rng, int(self.settlement_count.value()))

        if self.roads_enabled.isChecked():
            if settlements:
                roads = generate_road_network(self._cells, settlements)
                # extra random connections among settlements
                extra = max(0, int(self.road_count.value()))
                if extra > 0 and len(settlements) >= 3:
                    for _ in range(extra):
                        a = rng.choice(settlements)
                        b = rng.choice(settlements)
                        if a != b:
                            from .generator import astar_path
                            p = astar_path(self._cells, a, b)
                            if p:
                                roads.append(p)
                self._roads = roads
            else:
                self._roads = _roads_random
        else:
            self._roads = []

        # clear cards on full regen
        self._hex_cards = {}
        self._undo_stack = []
        self._selected = None
        self.card_preview.clear()
        self.sel_label.setText("—")

        self._update_key_preview()
        self.on_redraw()
        self.ctx.log(f"[HexMap] Generated {cfg.width}x{cfg.height} (seed {cfg.seed})")

    def on_redraw(self):
        if not self._cells:
            return
        cfg = RenderConfig(
            hex_size=int(self.hex_size.value()),
            show_grid=bool(self.show_grid.isChecked()),
            show_labels=bool(self.show_labels.isChecked()),
            show_poi=bool(self.show_poi.isChecked()),
            show_rivers=bool(self.rivers_enabled.isChecked()),
            show_roads=bool(self.roads_enabled.isChecked()),
        )
        scene = build_scene(
            self._cells,
            width=int(self.w_spin.value()),
            height=int(self.h_spin.value()),
            cfg=cfg,
            rivers=self._rivers,
            roads=self._roads
        )
        self._set_scene(scene)

    def _update_key_preview(self):
        if not self._cells:
            self.key_preview.clear()
            return

        cfg = self._make_cfg()
        counts = build_key(self._cells)
        pois = build_poi_list(self._cells)

        lines: List[str] = []
        lines.append(f"# Hex Map Key ({cfg.width}×{cfg.height})")
        lines.append("")

        lines.append("## Terrain")
        for terr, n in counts.items():
            lines.append(f"- **{terr}**: {n}")

        lines.append("")
        lines.append("## Points of Interest")
        if pois:
            lines.extend([f"- {p}" for p in pois])
        else:
            lines.append("- (none)")

        self.key_preview.setPlainText("\n".join(lines))

    # ---------- Selection, painting, editing ----------

    def on_hex_clicked(self, q: int, r: int):
        if not self._cells:
            return
        coord = (int(q), int(r))
        if coord not in self._cells:
            return

        # paint mode?
        if self.paint_mode.isChecked():
            terr = self.paint_combo.currentText().strip()
            if terr:
                self._paint_terrain(coord, terr)
            return

        # selection mode
        self._selected = coord
        self._sync_selected_editor()
        self._show_or_roll_card(coord)

    def _sync_selected_editor(self):
        if not self._selected:
            return
        q, r = self._selected
        self.sel_label.setText(f"{q},{r}")
        cell = self._cells.get((q, r))
        if not cell:
            return
        self._refresh_terrain_lists()
        # set editor terrain
        idx = self.terrain_combo.findText(cell.terrain)
        if idx >= 0:
            self.terrain_combo.setCurrentIndex(idx)
        self.poi_edit.setText(cell.poi or "")

    def _paint_terrain(self, coord: Coord, new_terrain: str):
        cell = self._cells.get(coord)
        if not cell:
            return
        old = cell.terrain
        if old == new_terrain:
            return

        # record undo
        self._undo_stack.append({"coord": coord, "old": old, "new": new_terrain})
        cell.terrain = new_terrain

        # terrain change may change content relevance; don't auto-wipe locked cards
        key = f"{coord[0]},{coord[1]}"
        if key in self._hex_cards and not bool(self._hex_cards[key].get("locked", False)):
            self._hex_cards.pop(key, None)

        self.on_redraw()

    def _sync_paint_ui(self, checked: bool):
        self.btn_undo.setEnabled(True)

    def on_undo(self):
        if not self._undo_stack:
            return
        action = self._undo_stack.pop()
        coord = action.get("coord")
        if not coord:
            return
        cell = self._cells.get(tuple(coord))
        if not cell:
            return
        cell.terrain = action.get("old", cell.terrain)
        # unlockable card: drop if not locked
        key = f"{coord[0]},{coord[1]}"
        if key in self._hex_cards and not bool(self._hex_cards[key].get("locked", False)):
            self._hex_cards.pop(key, None)

        self.on_redraw()
        if self._selected == tuple(coord):
            self._sync_selected_editor()
            self._show_or_roll_card(tuple(coord), force=False)

    def on_apply_hex(self):
        if not self._selected:
            return
        cell = self._cells.get(self._selected)
        if not cell:
            return
        new_terrain = self.terrain_combo.currentText().strip()
        if new_terrain and new_terrain != cell.terrain:
            # treat as paint (undoable)
            self._paint_terrain(self._selected, new_terrain)

        cell.poi = (self.poi_edit.text() or "").strip() or None
        self._update_key_preview()
        self.on_redraw()

    def on_clear_poi(self):
        if not self._selected:
            return
        cell = self._cells.get(self._selected)
        if not cell:
            return
        cell.poi = None
        self.poi_edit.setText("")
        self._update_key_preview()
        self.on_redraw()

    # ---------- Content cards ----------

    def _card_key(self, coord: Coord) -> str:
        return f"{coord[0]},{coord[1]}"

    def _show_or_roll_card(self, coord: Coord, force: bool = False):
        ck = self._card_key(coord)
        existing = self._hex_cards.get(ck)
        if existing and existing.get("card") and (existing.get("locked") or not force):
            self.card_preview.setPlainText(self._format_card_md(coord, existing.get("card", {}), locked=bool(existing.get("locked"))))
            self.btn_lock_card.setText("Unlock Card" if bool(existing.get("locked")) else "Lock Card")
            return

        self._roll_card(coord)

    def _roll_card(self, coord: Coord):
        cell = self._cells.get(coord)
        if not cell:
            return
        ck = self._card_key(coord)
        locked = bool(self._hex_cards.get(ck, {}).get("locked", False))
        if locked:
            # locked card: just display
            self.card_preview.setPlainText(self._format_card_md(coord, self._hex_cards[ck]["card"], locked=True))
            return

        rng = self.ctx.derive_rng(int(self.seed_spin.value()), "hexmap", "card", coord[0], coord[1])
        card = generate_hex_content(cell.terrain, rng)
        # small bonus: include POI/settlement context
        ctx_bits = {}
        if cell.poi:
            ctx_bits["poi"] = cell.poi
        if cell.settlement:
            ctx_bits["settlement"] = cell.settlement
        card2 = {"context": ctx_bits, **card}
        self._hex_cards[ck] = {"locked": False, "card": card2}

        self.card_preview.setPlainText(self._format_card_md(coord, card2, locked=False))
        self.btn_lock_card.setText("Lock Card")

    def _format_card_md(self, coord: Coord, card: Dict[str, Any], locked: bool) -> str:
        cell = self._cells.get(coord)
        head = f"# Hex {coord[0]},{coord[1]}"
        if cell:
            head += f" — {cell.terrain}"
        if locked:
            head += " 🔒"
        lines = [head, ""]
        ctx = card.get("context", {}) if isinstance(card, dict) else {}
        if isinstance(ctx, dict):
            if "settlement" in ctx and isinstance(ctx["settlement"], dict):
                s = ctx["settlement"]
                lines.append(f"**Settlement:** {s.get('kind','Settlement')} of {s.get('name','(unnamed)')}")
            if ctx.get("poi"):
                lines.append(f"**POI:** {ctx.get('poi')}")
            if len(lines) > 2:
                lines.append("")

        def section(title: str, items: List[str]):
            if not items:
                return
            lines.append(f"## {title}")
            for it in items:
                lines.append(f"- {it}")
            lines.append("")

        section("Encounters", list(card.get("encounters", []) or []))
        section("Hazards", list(card.get("hazards", []) or []))
        section("Resources", list(card.get("resources", []) or []))

        return "\n".join(lines).strip() + "\n"

    def on_roll_card(self):
        if not self._selected:
            return
        self._roll_card(self._selected)

    def on_toggle_lock_card(self):
        if not self._selected:
            return
        ck = self._card_key(self._selected)
        entry = self._hex_cards.get(ck)
        if not entry:
            # create one then lock
            self._roll_card(self._selected)
            entry = self._hex_cards.get(ck)
            if not entry:
                return
        entry["locked"] = not bool(entry.get("locked", False))
        self.btn_lock_card.setText("Unlock Card" if bool(entry.get("locked")) else "Lock Card")
        self.card_preview.setPlainText(self._format_card_md(self._selected, entry.get("card", {}), locked=bool(entry.get("locked"))))

    def on_send_card_to_scratchpad(self):
        if not self._selected:
            return
        ck = self._card_key(self._selected)
        entry = self._hex_cards.get(ck)
        if not entry or not entry.get("card"):
            self._roll_card(self._selected)
            entry = self._hex_cards.get(ck)
            if not entry or not entry.get("card"):
                return
        md = self._format_card_md(self._selected, entry["card"], locked=bool(entry.get("locked")))
        self.ctx.scratchpad_add(md, tags=["Map", "HexMap", "HexCard", f"Hex:{ck}"])
        self.ctx.log(f"[HexMap] Sent hex card {ck} to scratchpad.")

    # ---------- Export ----------

    def on_export_png(self):
        if not self._scene:
            return
        default_dir = str((self.ctx.project_dir / "exports").resolve())
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Hex Map PNG",
            str(Path(default_dir) / "hexmap.png"),
            "PNG Image (*.png)"
        )
        if not path:
            return
        img = scene_to_image(self._scene)
        ok = img.save(path, "PNG")
        if ok:
            self.ctx.log(f"[HexMap] Exported PNG: {path}")
        else:
            QMessageBox.warning(self, "Export Failed", "Could not write PNG.")

    def on_export_svg(self):
        if not self._scene:
            return
        if not can_export_svg():
            QMessageBox.warning(self, "SVG Unavailable", "QtSvg is not available in this PySide6 install.")
            return
        default_dir = str((self.ctx.project_dir / "exports").resolve())
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Hex Map SVG",
            str(Path(default_dir) / "hexmap.svg"),
            "SVG Image (*.svg)"
        )
        if not path:
            return
        try:
            scene_to_svg(self._scene, path)
            self.ctx.log(f"[HexMap] Exported SVG: {path}")
        except Exception as e:
            QMessageBox.warning(self, "Export Failed", f"Could not write SVG:\n{e}")

    def on_export_md(self):
        if not self._cells:
            return
        default_dir = str((self.ctx.project_dir / "exports").resolve())
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Hex Map Markdown",
            str(Path(default_dir) / "hexmap_key.md"),
            "Markdown (*.md)"
        )
        if not path:
            return
        md = self.key_preview.toPlainText()
        try:
            Path(path).write_text(md, encoding="utf-8")
            self.ctx.log(f"[HexMap] Exported Markdown: {path}")
        except Exception as e:
            QMessageBox.warning(self, "Export Failed", f"Could not write Markdown:\n{e}")

    def _build_gazetteer_md(self) -> str:
        cfg = self._make_cfg()
        theme = self.theme_combo.currentText()
        lines = [
            f"# Hex Map Gazetteer",
            "",
            f"- **Theme:** {theme}",
            f"- **Size:** {cfg.width} x {cfg.height}",
            f"- **Seed:** {cfg.seed}",
            "",
        ]

        # terrain counts
        counts: Dict[str, int] = {}
        for c in self._cells.values():
            counts[c.terrain] = counts.get(c.terrain, 0) + 1
        lines.append("## Terrain Summary")
        for t, n in sorted(counts.items(), key=lambda x: (-x[1], x[0])):
            lines.append(f"- **{t}**: {n}")
        lines.append("")

        # settlements
        settlements = []
        for (q, r), c in self._cells.items():
            if c.settlement and isinstance(c.settlement, dict):
                settlements.append(((q, r), c.settlement))
        if settlements:
            lines.append("## Settlements")
            for (q, r), s in sorted(settlements, key=lambda x: (x[0][1], x[0][0])):
                lines.append(f"### {s.get('kind','Settlement')} of {s.get('name','(unnamed)')} ({q},{r})")
                lines.append(f"- Terrain: {self._cells[(q,r)].terrain}")
                if self._cells[(q,r)].poi:
                    lines.append(f"- POI: {self._cells[(q,r)].poi}")
                lines.append("")
        else:
            lines.append("## Settlements")
            lines.append("_None generated._")
            lines.append("")

        # POIs
        lines.append("## POIs")
        poi_lines = []
        for (q, r), c in sorted(self._cells.items(), key=lambda x: (x[0][1], x[0][0])):
            if c.poi:
                poi_lines.append(f"- **{q},{r}** — {c.poi} ({c.terrain})")
        if poi_lines:
            lines.extend(poi_lines)
        else:
            lines.append("_None._")
        lines.append("")

        # Interesting hexes with cards (POI or settlement)
        lines.append("## Hex Cards (Highlights)")
        for (q, r), c in sorted(self._cells.items(), key=lambda x: (x[0][1], x[0][0])):
            if not (c.poi or c.settlement):
                continue
            ck = f"{q},{r}"
            entry = self._hex_cards.get(ck)
            if not entry or not entry.get("card"):
                # generate for export if missing (unlocked)
                rng = self.ctx.derive_rng(int(cfg.seed), "hexmap", "card", q, r)
                card = generate_hex_content(c.terrain, rng)
                ctx_bits = {}
                if c.poi:
                    ctx_bits["poi"] = c.poi
                if c.settlement:
                    ctx_bits["settlement"] = c.settlement
                card2 = {"context": ctx_bits, **card}
                self._hex_cards[ck] = {"locked": False, "card": card2}
                entry = self._hex_cards[ck]

            lines.append(self._format_card_md((q, r), entry["card"], locked=bool(entry.get("locked"))).rstrip())
            lines.append("")
        return "\n".join(lines).strip() + "\n"

    
    def _ensure_card_entry(self, q: int, r: int):
        """Ensure a content card exists for the given hex; generate deterministically if missing."""
        if not self._cells:
            return None
        cell = self._cells.get((q, r))
        if not cell:
            return None

        ck = f"{q},{r}"
        entry = self._hex_cards.get(ck)
        if entry and entry.get("card"):
            return entry

        cfg = self._make_cfg()
        rng = self.ctx.derive_rng(int(cfg.seed), "hexmap", "card", q, r)
        card = generate_hex_content(cell.terrain, rng)

        ctx_bits = {}
        if cell.poi:
            ctx_bits["poi"] = cell.poi
        if cell.settlement:
            ctx_bits["settlement"] = cell.settlement

        card2 = {"context": ctx_bits, **card}
        entry = {"locked": False, "card": card2}
        self._hex_cards[ck] = entry
        return entry

    def _build_all_hex_cards_md(self) -> str:
        """Markdown containing every hex's content card (generating missing ones)."""
        if not self._cells:
            return ""
        lines = ["# Hex Content Cards", ""]
        for (q, r) in sorted(self._cells.keys(), key=lambda x: (x[1], x[0])):
            entry = self._ensure_card_entry(q, r)
            if not entry:
                continue
            lines.append(self._format_card_md((q, r), entry["card"], locked=bool(entry.get("locked"))).rstrip())
            lines.append("")
        return "\n".join(lines).strip() + "\n"

    def _export_hex_cards(self, pack_dir: Path):
        """Write per-hex card markdown files + a combined hex_cards.md."""
        if not self._cells:
            return

        cards_dir = pack_dir / "hex_cards"
        cards_dir.mkdir(parents=True, exist_ok=True)

        # Combined
        all_md = self._build_all_hex_cards_md()
        (pack_dir / "hex_cards.md").write_text(all_md, encoding="utf-8")

        # Individual files + index
        index_lines = ["# Hex Cards Index", "", "Files in this folder:", ""]
        for (q, r) in sorted(self._cells.keys(), key=lambda x: (x[1], x[0])):
            entry = self._ensure_card_entry(q, r)
            if not entry:
                continue
            fname = f"hex_{q}_{r}.md"
            md = self._format_card_md((q, r), entry["card"], locked=bool(entry.get("locked")))
            (cards_dir / fname).write_text(md, encoding="utf-8")
            index_lines.append(f"- [{q},{r}]({fname})")
        index_lines.append("")
        (cards_dir / "index.md").write_text("\n".join(index_lines), encoding="utf-8")

    def on_export_session_pack(self):
            if not self._cells or not self._scene:
                QMessageBox.information(self, "Export", "Generate a map first before exporting.")
                return

            # Ensure key preview reflects current map (terrain edits, POIs, etc.)
            try:
                self._update_key_preview()
            except Exception:
                pass

            cfg = self._make_cfg()
            try:
                pack = self.ctx.export_manager.create_session_pack("hexmap", seed=int(cfg.seed))
            except Exception as e:
                QMessageBox.warning(self, "Export Failed", f"Could not create session pack:\n{e}")
                return

            written = []

            # Write images
            try:
                img = scene_to_image(self._scene)
                png_path = pack / "map.png"
                img.save(str(png_path), "PNG")
                written.append(png_path)
            except Exception as e:
                QMessageBox.warning(self, "Export Failed", f"Could not write map.png:\n{e}")
                return

            # Optional SVG (depends on QtSvg)
            try:
                scene_to_svg(self._scene, str(pack / "map.svg"))
                written.append(pack / "map.svg")
            except Exception:
                pass

            # Write markdowns
            try:
                (pack / "hex_key.md").write_text(self.key_preview.toPlainText(), encoding="utf-8")
                written.append(pack / "hex_key.md")
                (pack / "gazetteer.md").write_text(self._build_gazetteer_md(), encoding="utf-8")
                written.append(pack / "gazetteer.md")
            except Exception as e:
                QMessageBox.warning(self, "Export Failed", f"Could not write markdown:\n{e}")
                return

            # Write per-hex content cards (combined + individual files)
            try:
                self._export_hex_cards(pack)
                written.append(pack / "hex_cards.md")
                written.append(pack / "hex_cards" / "index.md")
            except Exception as e:
                QMessageBox.warning(self, "Export Failed", f"Could not export hex content cards:\n{e}")
                return

            self.ctx.log(f"[HexMap] Exported session pack: {pack}")
            for p in written:
                try:
                    self.ctx.log(f"[HexMap]  - {p}")
                except Exception:
                    pass
            QMessageBox.information(self, "Export Complete", f"Exported session pack to:\n{pack}")

    # ---------- Scratchpad ----------

    def on_send_scratchpad(self):
        md = self.key_preview.toPlainText().strip()
        if not md:
            return
        self.ctx.scratchpad_add(md, tags=["Map", "HexMap"])
        self.ctx.log("[HexMap] Sent key/POIs to scratchpad.")

    def on_copy_md(self):
        md = self.key_preview.toPlainText()
        QApplication.clipboard().setText(md)
        self.ctx.log("[HexMap] Copied markdown to clipboard.")

    # ---------- Persistence ----------

    def serialize_state(self) -> dict:
        # Save UI + generated map state (so edits & cards persist across restarts)
        state: Dict[str, Any] = {
            "version": 2,
            "theme_index": int(self.theme_combo.currentIndex()),
            "w": int(self.w_spin.value()),
            "h": int(self.h_spin.value()),
            "seed": int(self.seed_spin.value()),
            "poi_density": float(self.poi_spin.value()),
            "hex_size": int(self.hex_size.value()),
            "show_grid": bool(self.show_grid.isChecked()),
            "show_labels": bool(self.show_labels.isChecked()),
            "show_poi": bool(self.show_poi.isChecked()),
            "rivers_enabled": bool(self.rivers_enabled.isChecked()),
            "river_count": int(self.river_count.value()),
            "settlements_enabled": bool(self.settlements_enabled.isChecked()),
            "settlement_count": int(self.settlement_count.value()),
            "roads_enabled": bool(self.roads_enabled.isChecked()),
            "road_count": int(self.road_count.value()),
            "preview_open": bool(self._preview_win is not None),
        }

        if self._cells:
            cells_out = []
            for (q, r), c in self._cells.items():
                cells_out.append({
                    "q": int(q),
                    "r": int(r),
                    "terrain": str(c.terrain),
                    "poi": c.poi,
                    "settlement": c.settlement,
                })
            state["map"] = {
                "cells": cells_out,
                "rivers": [[list(p) for p in path] for path in self._rivers],
                "roads": [[list(p) for p in path] for path in self._roads],
                "cards": self._hex_cards,
            }
        return state

    def load_state(self, state: dict) -> None:
        if not state:
            self._refresh_terrain_lists()
            return

        # UI basics
        for key, widget, cast in [
            ("w", self.w_spin, int),
            ("h", self.h_spin, int),
            ("seed", self.seed_spin, int),
            ("poi_density", self.poi_spin, float),
            ("hex_size", self.hex_size, int),
            ("river_count", self.river_count, int),
            ("settlement_count", self.settlement_count, int),
            ("road_count", self.road_count, int),
        ]:
            if key in state:
                try:
                    widget.setValue(cast(state.get(key)))
                except Exception:
                    pass

        # checkboxes
        for key, cb in [
            ("show_grid", self.show_grid),
            ("show_labels", self.show_labels),
            ("show_poi", self.show_poi),
            ("rivers_enabled", self.rivers_enabled),
            ("roads_enabled", self.roads_enabled),
            ("settlements_enabled", self.settlements_enabled),
        ]:
            if key in state:
                try:
                    cb.setChecked(bool(state.get(key)))
                except Exception:
                    pass

        # theme selection
        try:
            idx = int(state.get("theme_index", 0))
            if 0 <= idx < self.theme_combo.count():
                self.theme_combo.setCurrentIndex(idx)
        except Exception:
            pass
        self.on_theme_changed(self.theme_combo.currentIndex())

        # load map
        mp = state.get("map", {})
        if isinstance(mp, dict) and mp.get("cells"):
            cells: Dict[Coord, HexCell] = {}
            try:
                for d in mp.get("cells", []):
                    q = int(d.get("q", 0)); r = int(d.get("r", 0))
                    cells[(q, r)] = HexCell(
                        q=q, r=r,
                        terrain=str(d.get("terrain", "Plains")),
                        poi=d.get("poi") or None,
                        settlement=d.get("settlement", None),
                    )
                self._cells = cells
                self._rivers = [[tuple(p) for p in path] for path in mp.get("rivers", [])]
                self._roads = [[tuple(p) for p in path] for path in mp.get("roads", [])]
                self._hex_cards = dict(mp.get("cards", {}) or {})
                self._update_key_preview()
                self.on_redraw()
            except Exception as e:
                self.ctx.log(f"[HexMap] Failed to load saved map state: {e}")

        if bool(state.get("preview_open", False)):
            self._ensure_preview(show=False)
