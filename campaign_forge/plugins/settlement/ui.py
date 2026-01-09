
from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence, QPainter
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QComboBox, QSpinBox, QCheckBox, QPushButton,
    QTabWidget, QTextEdit, QListWidget, QListWidgetItem,
    QMessageBox, QSplitter, QLabel, QMainWindow, QToolBar,
    QGraphicsView, QGraphicsScene
)

from campaign_forge.core.context import ForgeContext
from .generator import (
    SETTLEMENT_TYPES, POP_BANDS, AGES, TERRAINS,
    generate_settlement, settlement_to_dict, settlement_from_dict, Settlement
)
from .map_render import MapRenderOptions, build_scene
from .exports import export_png, export_svg, export_markdown_key, export_markdown_locations, export_markdown_rumors


class _ZoomPanView(QGraphicsView):
    def __init__(self):
        super().__init__()
        try:
            self.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        except AttributeError:
            # Compatibility with older bindings
            self.setRenderHint(QPainter.Antialiasing, True)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)

    def wheelEvent(self, event):
        if event.angleDelta().y() == 0:
            return
        factor = 1.18 if event.angleDelta().y() > 0 else 1 / 1.18
        self.scale(factor, factor)


class MapPreviewWindow(QMainWindow):
    def __init__(self, parent: QWidget, settlement: Settlement, opts: MapRenderOptions):
        super().__init__(parent)
        self.setWindowTitle("Settlement Map Preview")
        self._settlement = settlement
        self._opts = opts

        self._view = _ZoomPanView()
        self._scene: Optional[QGraphicsScene] = None
        self.setCentralWidget(self._view)

        tb = QToolBar("Map")
        self.addToolBar(tb)

        self._act_districts = QAction("Districts", self, checkable=True, checked=opts.show_districts)
        self._act_labels = QAction("Labels", self, checkable=True, checked=opts.show_labels)
        self._act_roads = QAction("Roads", self, checkable=True, checked=opts.show_roads)
        self._act_river = QAction("River", self, checkable=True, checked=opts.show_river)
        self._act_walls = QAction("Walls", self, checkable=True, checked=opts.show_walls)
        self._act_landmarks = QAction("Landmarks", self, checkable=True, checked=opts.show_landmarks)
        self._act_factions = QAction("Faction Overlay", self, checkable=True, checked=opts.show_factions)

        for a in [self._act_districts, self._act_labels, self._act_roads, self._act_river, self._act_walls, self._act_landmarks, self._act_factions]:
            a.triggered.connect(self._refresh)
            tb.addAction(a)

        tb.addSeparator()
        reset = QAction("Reset View", self)
        reset.triggered.connect(self._reset_view)
        tb.addAction(reset)

        self._refresh()
        self._reset_view()

    def _collect_opts(self) -> MapRenderOptions:
        return MapRenderOptions(
            show_districts=self._act_districts.isChecked(),
            show_labels=self._act_labels.isChecked(),
            show_roads=self._act_roads.isChecked(),
            show_river=self._act_river.isChecked(),
            show_walls=self._act_walls.isChecked(),
            show_landmarks=self._act_landmarks.isChecked(),
            show_factions=self._act_factions.isChecked(),
        )

    def _refresh(self):
        self._opts = self._collect_opts()
        self._scene = build_scene(self._settlement, self._opts)
        self._view.setScene(self._scene)

    def _reset_view(self):
        if self._scene is None:
            return
        self._view.resetTransform()
        self._view.fitInView(self._scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)


class SettlementWidget(QWidget):
    """
    Settlement / Town Generator plugin.
    """
    def __init__(self, ctx: ForgeContext):
        super().__init__()
        self.ctx = ctx
        self._version = 1

        self._generated: Optional[Settlement] = None
        self._map_opts = MapRenderOptions()  # default for exports / preview

        self._build_ui()

    # ------------------ UI ------------------

    def _build_ui(self):
        root = QVBoxLayout(self)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        root.addWidget(splitter)

        # Left controls panel
        left = QWidget()
        left_layout = QVBoxLayout(left)
        splitter.addWidget(left)

        form = QFormLayout()
        left_layout.addLayout(form)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Leave blank for generated name")
        form.addRow("Name", self.name_edit)

        self.type_combo = QComboBox()
        self.type_combo.addItems(SETTLEMENT_TYPES)
        self.type_combo.setCurrentText("Town")
        form.addRow("Type", self.type_combo)

        self.pop_combo = QComboBox()
        self.pop_combo.addItems(POP_BANDS)
        self.pop_combo.setCurrentText("Hundreds")
        form.addRow("Population", self.pop_combo)

        self.age_combo = QComboBox()
        self.age_combo.addItems(AGES)
        self.age_combo.setCurrentText("Established")
        form.addRow("Age", self.age_combo)

        self.terrain_combo = QComboBox()
        self.terrain_combo.addItems(TERRAINS)
        self.terrain_combo.setCurrentText("Plains")
        form.addRow("Terrain", self.terrain_combo)

        self.district_spin = QSpinBox()
        self.district_spin.setRange(3, 12)
        self.district_spin.setValue(7)
        form.addRow("Districts", self.district_spin)

        self.chk_river = QCheckBox("Include river")
        self.chk_river.setChecked(True)
        form.addRow("", self.chk_river)

        self.chk_walls = QCheckBox("Include walls")
        self.chk_walls.setChecked(True)
        form.addRow("", self.chk_walls)

        self.btn_generate = QPushButton("Generate Settlement")
        self.btn_generate.clicked.connect(self.on_generate)
        left_layout.addWidget(self.btn_generate)

        self.btn_preview = QPushButton("Preview Map (New Window)")
        self.btn_preview.clicked.connect(self.on_preview_map)
        left_layout.addWidget(self.btn_preview)

        self.btn_export = QPushButton("Export Session Pack")
        self.btn_export.clicked.connect(self.on_export)
        left_layout.addWidget(self.btn_export)

        self.btn_scratch = QPushButton("Send Summary to Scratchpad")
        self.btn_scratch.clicked.connect(self.on_send_to_scratchpad)
        left_layout.addWidget(self.btn_scratch)

        left_layout.addStretch(1)

        # Right output panel
        right = QWidget()
        right_layout = QVBoxLayout(right)
        splitter.addWidget(right)

        self.tabs = QTabWidget()
        right_layout.addWidget(self.tabs)

        self.summary_view = QTextEdit()
        self.summary_view.setReadOnly(True)
        self.tabs.addTab(self.summary_view, "Summary")

        self.factions_view = QTextEdit()
        self.factions_view.setReadOnly(True)
        self.tabs.addTab(self.factions_view, "Factions")

        self.locations_view = QTextEdit()
        self.locations_view.setReadOnly(True)
        self.tabs.addTab(self.locations_view, "Locations")

        self.rumors_view = QTextEdit()
        self.rumors_view.setReadOnly(True)
        self.tabs.addTab(self.rumors_view, "Rumors & Trouble")

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([360, 900])

        # Keyboard shortcut: Ctrl+G to generate
        act_gen = QAction(self)
        act_gen.setShortcut(QKeySequence("Ctrl+G"))
        act_gen.triggered.connect(self.on_generate)
        self.addAction(act_gen)

    # ------------------ actions ------------------

    def on_generate(self):
        try:
            # Deterministic per-click RNG
            it = getattr(self, "_gen_count", 0)
            setattr(self, "_gen_count", it + 1)

            rng = self.ctx.derive_rng(self.ctx.master_seed, "settlement", "generate", it)

            s = generate_settlement(
                rng,
                name=self.name_edit.text().strip() or None,
                settlement_type=self.type_combo.currentText(),
                population_band=self.pop_combo.currentText(),
                age=self.age_combo.currentText(),
                terrain=self.terrain_combo.currentText(),
                tags=[],
                district_count=int(self.district_spin.value()),
                has_river=self.chk_river.isChecked(),
                has_walls=self.chk_walls.isChecked(),
            )
            self._generated = s

            self._refresh_views()
            self.ctx.log(f"[Settlement] Generated: {s.name} ({s.settlement_type})")
        except Exception as e:
            self.ctx.log(f"[Settlement] ERROR during generation: {e}")
            QMessageBox.critical(self, "Settlement Generator", f"Generation failed:\n{e}")

    def on_preview_map(self):
        if not self._generated:
            QMessageBox.information(self, "Settlement Generator", "Generate a settlement first.")
            return
        w = MapPreviewWindow(self, self._generated, self._map_opts)
        w.resize(1100, 800)
        w.show()
        # Keep a reference so it doesn't get GC'd
        self._preview = w

    def on_export(self):
        if not self._generated:
            QMessageBox.information(self, "Settlement Generator", "Generate a settlement first.")
            return
        try:
            s = self._generated
            pack = self.ctx.export_manager.create_session_pack(f"settlement_{s.name}", seed=self.ctx.master_seed)

            # Export files
            export_png(pack / "map.png", s, self._map_opts, scale=1.0)
            export_svg(pack / "map.svg", s, self._map_opts)
            export_markdown_key(pack / "district_key.md", s)
            export_markdown_locations(pack / "locations.md", s)
            export_markdown_rumors(pack / "rumors.md", s)

            self.ctx.log(f"[Settlement] Exported session pack: {pack}")
            QMessageBox.information(self, "Settlement Generator", f"Exported to:\n{pack}")
        except Exception as e:
            self.ctx.log(f"[Settlement] ERROR during export: {e}")
            QMessageBox.critical(self, "Settlement Generator", f"Export failed:\n{e}")

    def on_send_to_scratchpad(self):
        if not self._generated:
            QMessageBox.information(self, "Settlement Generator", "Generate a settlement first.")
            return
        s = self._generated
        text = self._build_markdown_summary(s)
        self.ctx.scratchpad_add(text, ["Settlement", "Town", f"Town:{s.name}"])
        self.ctx.log(f"[Settlement] Sent summary to scratchpad: {s.name}")

    # ------------------ rendering ------------------

    def _refresh_views(self):
        if not self._generated:
            return
        s = self._generated
        self.summary_view.setPlainText(self._build_markdown_summary(s))
        self.factions_view.setPlainText(self._build_markdown_factions(s))
        self.locations_view.setPlainText(self._build_markdown_locations(s))
        self.rumors_view.setPlainText(self._build_markdown_rumors(s))

    def _build_markdown_summary(self, s: Settlement) -> str:
        lines = []
        lines.append(f"# {s.name} — {s.settlement_type}")
        lines.append("")
        lines.append(f"- Terrain: **{s.terrain}**")
        lines.append(f"- Population: **{s.population_band}**")
        lines.append(f"- Age: **{s.age}**")
        lines.append(f"- River: **{'Yes' if s.has_river else 'No'}**, Walls: **{'Yes' if s.has_walls else 'No'}**")
        lines.append("")
        lines.append("## Problems")
        for p in s.problems:
            lines.append(f"- {p}")
        lines.append("")
        lines.append("## Districts (at-a-glance)")
        for d in s.districts:
            lines.append(f"- **{d.name}** — {d.wealth} wealth, {d.law} law, {d.danger} danger")
        return "\n".join(lines)

    def _build_markdown_factions(self, s: Settlement) -> str:
        lines = []
        lines.append(f"# {s.name} — Factions")
        lines.append("")
        for f in s.factions:
            lines.append(f"## {f.name} ({f.kind})")
            lines.append(f"- Goal: {f.goal}")
            lines.append(f"- Method: {f.method}")
            lines.append(f"- Signature: {f.signature}")
            lines.append("")
        return "\n".join(lines)

    def _build_markdown_locations(self, s: Settlement) -> str:
        lines = []
        lines.append(f"# {s.name} — Locations")
        lines.append("")
        for d in s.districts:
            lines.append(f"## {d.name}")
            lines.append(f"*{d.kind} — Wealth {d.wealth}, Law {d.law}, Danger {d.danger}*")
            lines.append("")
            for loc in d.locations:
                lines.append(f"### {loc.name} ({loc.kind})")
                lines.append(f"- Owner: {loc.owner}")
                lines.append(f"- Hook: {loc.hook}")
                lines.append(f"- Secret: {loc.secret}")
                lines.append("")
        return "\n".join(lines)

    def _build_markdown_rumors(self, s: Settlement) -> str:
        lines = []
        lines.append(f"# {s.name} — Rumors & Trouble")
        lines.append("")
        lines.append("## Rumors (True)")
        for r in s.rumors_true:
            lines.append(f"- {r}")
        lines.append("")
        lines.append("## Rumors (Half-True)")
        for r in s.rumors_half:
            lines.append(f"- {r}")
        lines.append("")
        lines.append("## Rumors (False)")
        for r in s.rumors_false:
            lines.append(f"- {r}")
        return "\n".join(lines)

    # ------------------ state persistence ------------------

    def serialize_state(self) -> Dict[str, Any]:
        return {
            "version": self._version,
            "ui": {
                "name": self.name_edit.text(),
                "type": self.type_combo.currentText(),
                "population": self.pop_combo.currentText(),
                "age": self.age_combo.currentText(),
                "terrain": self.terrain_combo.currentText(),
                "districts": int(self.district_spin.value()),
                "has_river": self.chk_river.isChecked(),
                "has_walls": self.chk_walls.isChecked(),
            },
            "data": {
                "generated": settlement_to_dict(self._generated) if self._generated else None,
                "gen_count": int(getattr(self, "_gen_count", 0)),
            }
        }

    def load_state(self, state: Dict[str, Any]) -> None:
        try:
            if not state:
                return
            ver = state.get("version", 1)
            ui = state.get("ui", {}) if isinstance(state.get("ui", {}), dict) else {}
            self.name_edit.setText(ui.get("name", ""))
            self.type_combo.setCurrentText(ui.get("type", "Town"))
            self.pop_combo.setCurrentText(ui.get("population", "Hundreds"))
            self.age_combo.setCurrentText(ui.get("age", "Established"))
            self.terrain_combo.setCurrentText(ui.get("terrain", "Plains"))
            self.district_spin.setValue(int(ui.get("districts", 7)))
            self.chk_river.setChecked(bool(ui.get("has_river", True)))
            self.chk_walls.setChecked(bool(ui.get("has_walls", True)))

            data = state.get("data", {}) if isinstance(state.get("data", {}), dict) else {}
            setattr(self, "_gen_count", int(data.get("gen_count", 0)))

            gd = data.get("generated", None)
            if isinstance(gd, dict):
                self._generated = settlement_from_dict(gd)
                self._refresh_views()
        except Exception as e:
            self.ctx.log(f"[Settlement] WARNING: failed to load state: {e}")
