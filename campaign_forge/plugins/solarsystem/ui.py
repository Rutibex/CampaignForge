from __future__ import annotations

from typing import Any, Dict, Optional, Tuple
import random
import json

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QPushButton, QComboBox, QSpinBox, QCheckBox, QLineEdit,
    QTreeWidget, QTreeWidgetItem, QTextEdit, QLabel, QMessageBox
)

from .generator import SystemConfig, generate_system, iter_bodies, summarize_world, _load_table
from .map_window import SolarSystemMapWindow
from .exports import export_system_pack, system_overview_markdown, world_markdown


class SolarSystemWidget(QWidget):
    STATE_VERSION = 1

    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx
        self._iteration = 0
        self._seed_override: Optional[int] = None
        self._system: Optional[Dict[str, Any]] = None
        self._selected_body_id: Optional[str] = None
        self._map_win: Optional[SolarSystemMapWindow] = None

        self._presets = _load_table("presets.json")

        self._build_ui()

    # -------- UI --------

    def _build_ui(self):
        root = QVBoxLayout(self)

        # Controls
        controls = QHBoxLayout()
        root.addLayout(controls)

        form = QFormLayout()
        controls.addLayout(form, 1)

        self.cmb_star_count = QComboBox()
        self.cmb_star_count.addItems(["1", "2", "3"])
        form.addRow("Stars", self.cmb_star_count)

        self.spn_max_orbits = QSpinBox()
        self.spn_max_orbits.setRange(4, 24)
        self.spn_max_orbits.setValue(12)
        form.addRow("Max orbits", self.spn_max_orbits)

        self.cmb_realism = QComboBox()
        self.cmb_realism.addItems(["cinematic", "semi", "hard"])
        self.cmb_realism.setCurrentText("semi")
        form.addRow("Orbital realism", self.cmb_realism)

        self.cmb_life = QComboBox()
        self.cmb_life.addItems(["none", "rare", "common", "engineered"])
        self.cmb_life.setCurrentText("rare")
        form.addRow("Life rarity", self.cmb_life)

        self.cmb_civ = QComboBox()
        self.cmb_civ.addItems(["empty", "sparse", "clustered"])
        self.cmb_civ.setCurrentText("sparse")
        form.addRow("Civ density", self.cmb_civ)

        self.chk_exotics = QCheckBox("Include exotics")
        self.chk_exotics.setChecked(True)
        form.addRow(self.chk_exotics)

        self.chk_ruins = QCheckBox("Include ruins & relic hooks")
        self.chk_ruins.setChecked(True)
        form.addRow(self.chk_ruins)

        self.chk_trade = QCheckBox("Include trade goods")
        self.chk_trade.setChecked(True)
        form.addRow(self.chk_trade)

        self.chk_hazards = QCheckBox("Include hazards")
        self.chk_hazards.setChecked(True)
        form.addRow(self.chk_hazards)

        self.txt_seed = QLineEdit()
        self.txt_seed.setPlaceholderText("(optional) seed override integer")
        form.addRow("Seed override", self.txt_seed)

        self.cmb_preset = QComboBox()
        self.cmb_preset.addItem("(preset) — choose one", userData=None)
        for p in self._presets:
            self.cmb_preset.addItem(p["name"], userData=p)
        self.cmb_preset.currentIndexChanged.connect(self._apply_preset)
        form.addRow("Presets", self.cmb_preset)

        # Buttons
        btns = QVBoxLayout()
        controls.addLayout(btns)

        self.btn_generate = QPushButton("Generate System")
        self.btn_generate.clicked.connect(self.on_generate)
        btns.addWidget(self.btn_generate)

        self.btn_map = QPushButton("Open Map Window")
        self.btn_map.clicked.connect(self.on_open_map)
        btns.addWidget(self.btn_map)

        self.btn_export = QPushButton("Export Session Pack")
        self.btn_export.clicked.connect(self.on_export)
        btns.addWidget(self.btn_export)

        self.btn_scratch = QPushButton("Send Summaries to Scratchpad")
        self.btn_scratch.clicked.connect(self.on_send_scratchpad)
        btns.addWidget(self.btn_scratch)

        btns.addStretch(1)

        # Content area: tree + detail
        body = QHBoxLayout()
        root.addLayout(body, 1)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Body", "Type", "Life", "Inhabited"])
        self.tree.itemSelectionChanged.connect(self.on_tree_select)
        body.addWidget(self.tree, 1)

        self.detail = QTextEdit()
        self.detail.setReadOnly(True)
        body.addWidget(self.detail, 2)

        self.status = QLabel("Ready")
        root.addWidget(self.status)

    def _apply_preset(self):
        p = self.cmb_preset.currentData()
        if not p:
            return
        # Gentle: set a few knobs and seed hint
        notes = p.get("notes", "")
        seed_hint = p.get("seed_hint", None)
        if seed_hint is not None:
            self.txt_seed.setText(str(seed_hint))
        # simple heuristics from text
        low = (notes or "").lower()
        if "trinary" in low or "three" in low:
            self.cmb_star_count.setCurrentText("3")
        elif "binary" in low:
            self.cmb_star_count.setCurrentText("2")
        else:
            self.cmb_star_count.setCurrentText("1")
        if "empty" in low:
            self.cmb_civ.setCurrentText("empty")
        elif "contested" in low or "war" in low:
            self.cmb_civ.setCurrentText("clustered")
        self.status.setText(f"Preset applied: {p.get('name')} — {notes}")

    # -------- generation --------

    def _read_cfg(self) -> SystemConfig:
        return SystemConfig(
            star_count=int(self.cmb_star_count.currentText()),
            max_orbits=int(self.spn_max_orbits.value()),
            orbital_realism=str(self.cmb_realism.currentText()),
            life_rarity=str(self.cmb_life.currentText()),
            civ_density=str(self.cmb_civ.currentText()),
            include_exotics=bool(self.chk_exotics.isChecked()),
            include_ruins=bool(self.chk_ruins.isChecked()),
            include_trade=bool(self.chk_trade.isChecked()),
            include_hazards=bool(self.chk_hazards.isChecked()),
        )

    def _get_rng_and_seed(self) -> Tuple[random.Random, Optional[int]]:
        seed = None
        txt = (self.txt_seed.text() or "").strip()
        if txt:
            try:
                seed = int(txt)
            except Exception:
                seed = None

        # Prefer ForgeContext derived RNG
        if hasattr(self.ctx, "derive_rng") and hasattr(self.ctx, "master_seed"):
            base = getattr(self.ctx, "master_seed")
            # If seed override exists, use it instead of master seed
            master = seed if seed is not None else base
            try:
                rng = self.ctx.derive_rng(master, "solarsystem", "generate", self._iteration)
                return rng, master
            except Exception:
                pass

        # Fallback
        master = seed if seed is not None else 1337
        rng = random.Random((master, "solarsystem", self._iteration))
        return rng, master

    def on_generate(self):
        self._iteration += 1
        cfg = self._read_cfg()
        rng, master = self._get_rng_and_seed()
        try:
            self._system = generate_system(rng, cfg)
            self._system["_meta"] = {
                "plugin": "solarsystem",
                "state_version": self.STATE_VERSION,
                "iteration": self._iteration,
                "seed": master,
                "cfg": cfg.__dict__,
            }
            self._populate_tree()
            self.detail.setPlainText(system_overview_markdown(self._system))
            self.status.setText(f"Generated: {self._system.get('name')} (seed {master}, iter {self._iteration})")
            if self._map_win:
                self._map_win.system = self._system
                self._map_win._draw_system()  # refresh
        except Exception as e:
            self._log(f"[solarsystem] generation failed: {e}")
            QMessageBox.critical(self, "Solar System", f"Generation failed:\n{e}")

    def _populate_tree(self):
        self.tree.clear()
        if not self._system:
            return
        for p in self._system.get("orbits", []) or []:
            pit = QTreeWidgetItem([
                p.get("name", "(planet)"),
                p.get("class", {}).get("name", "Planet"),
                "Yes" if p.get("has_life") else "No",
                "Yes" if p.get("inhabited") else "No",
            ])
            pit.setData(0, Qt.UserRole, p.get("id"))
            self.tree.addTopLevelItem(pit)
            for m in p.get("moons", []) or []:
                mit = QTreeWidgetItem([
                    m.get("name", "(moon)"),
                    m.get("class", {}).get("name", "Moon"),
                    "Yes" if m.get("has_life") else "No",
                    "Yes" if m.get("inhabited") else "No",
                ])
                mit.setData(0, Qt.UserRole, m.get("id"))
                pit.addChild(mit)
            pit.setExpanded(True)

    def on_tree_select(self):
        items = self.tree.selectedItems()
        if not items or not self._system:
            return
        body_id = items[0].data(0, Qt.UserRole)
        self._selected_body_id = body_id
        body = None
        for b in iter_bodies(self._system):
            if b.get("id") == body_id:
                body = b
                break
        if body:
            self.detail.setMarkdown(world_markdown(body))
            if self._map_win:
                self._map_win.select_body(body_id)

    def on_open_map(self):
        if not self._system:
            QMessageBox.information(self, "Solar System", "Generate a system first.")
            return

        if self._map_win is None:
            self._map_win = SolarSystemMapWindow(self._system, on_select=self._on_map_select)
        else:
            self._map_win.system = self._system
            self._map_win._draw_system()
        self._map_win.show()
        self._map_win.raise_()
        self._map_win.activateWindow()

    def _on_map_select(self, body_id: str):
        self._selected_body_id = body_id
        # Select corresponding tree item
        def walk(item: QTreeWidgetItem) -> Optional[QTreeWidgetItem]:
            if item.data(0, Qt.UserRole) == body_id:
                return item
            for i in range(item.childCount()):
                found = walk(item.child(i))
                if found:
                    return found
            return None

        for i in range(self.tree.topLevelItemCount()):
            it = self.tree.topLevelItem(i)
            found = walk(it)
            if found:
                self.tree.setCurrentItem(found)
                break

    def on_export(self):
        if not self._system:
            QMessageBox.information(self, "Solar System", "Generate a system first.")
            return
        seed = (self._system.get("_meta") or {}).get("seed")
        map_png = None
        map_svg = None
        try:
            # Ensure we have a map window instance to render
            if self._map_win is None:
                self._map_win = SolarSystemMapWindow(self._system, on_select=self._on_map_select)
            else:
                self._map_win.system = self._system
                self._map_win._draw_system()
            map_png = self._map_win.render_png_bytes()
            map_svg = self._map_win.render_svg_bytes()
        except Exception as e:
            self._log(f"[solarsystem] map render failed (continuing without images): {e}")

        try:
            out_dir = export_system_pack(self.ctx, self._system, seed=seed, map_png_bytes=map_png, map_svg_bytes=map_svg)
            self._log(f"[solarsystem] Exported session pack: {out_dir}")
            QMessageBox.information(self, "Solar System", f"Exported to:\n{out_dir}")
        except Exception as e:
            self._log(f"[solarsystem] export failed: {e}")
            QMessageBox.critical(self, "Solar System", f"Export failed:\n{e}")

    def on_send_scratchpad(self):
        if not self._system:
            QMessageBox.information(self, "Solar System", "Generate a system first.")
            return
        if not hasattr(self.ctx, "scratchpad_add"):
            QMessageBox.information(self, "Solar System", "Scratchpad service not available in this build.")
            return

        # One overview + per inhabited/life worlds
        try:
            self.ctx.scratchpad_add(
                text=system_overview_markdown(self._system),
                tags=["SolarSystem", "Map", "System"],
            )
            count = 0
            for b in iter_bodies(self._system):
                if b.get("inhabited") or b.get("has_life"):
                    tags = ["SolarSystem", "World"]
                    if b.get("inhabited"):
                        tags.append("Inhabited")
                    if b.get("has_life"):
                        tags.append("Life")
                    self.ctx.scratchpad_add(text=world_markdown(b), tags=tags)
                    count += 1
            self._log(f"[solarsystem] Sent to scratchpad: overview + {count} worlds")
            QMessageBox.information(self, "Solar System", f"Sent to scratchpad: {count} world summaries.")
        except Exception as e:
            self._log(f"[solarsystem] scratchpad send failed: {e}")
            QMessageBox.critical(self, "Solar System", f"Scratchpad send failed:\n{e}")

    # -------- state --------

    def serialize_state(self) -> Dict[str, Any]:
        cfg = self._read_cfg().__dict__
        state = {
            "version": self.STATE_VERSION,
            "iteration": self._iteration,
            "cfg": cfg,
            "seed_override": (self.txt_seed.text() or "").strip(),
            "system": self._system,
            "selected_body_id": self._selected_body_id,
        }
        return state

    def load_state(self, state: Dict[str, Any]) -> None:
        if not state:
            return
        try:
            ver = int(state.get("version", 1))
            cfg = state.get("cfg", {}) or {}
            # restore controls
            self.cmb_star_count.setCurrentText(str(cfg.get("star_count", 1)))
            self.spn_max_orbits.setValue(int(cfg.get("max_orbits", 12)))
            self.cmb_realism.setCurrentText(str(cfg.get("orbital_realism", "semi")))
            self.cmb_life.setCurrentText(str(cfg.get("life_rarity", "rare")))
            self.cmb_civ.setCurrentText(str(cfg.get("civ_density", "sparse")))
            self.chk_exotics.setChecked(bool(cfg.get("include_exotics", True)))
            self.chk_ruins.setChecked(bool(cfg.get("include_ruins", True)))
            self.chk_trade.setChecked(bool(cfg.get("include_trade", True)))
            self.chk_hazards.setChecked(bool(cfg.get("include_hazards", True)))

            self._iteration = int(state.get("iteration", 0))
            seed_override = state.get("seed_override", "")
            if seed_override:
                self.txt_seed.setText(str(seed_override))

            self._system = state.get("system", None)
            self._selected_body_id = state.get("selected_body_id", None)

            self._populate_tree()
            if self._system:
                self.detail.setPlainText(system_overview_markdown(self._system))
                if self._selected_body_id:
                    # select it
                    self.on_open_map()  # create map window if desired? keep lightweight: don't auto-open
            self.status.setText("State loaded")
        except Exception as e:
            self._log(f"[solarsystem] failed to load state: {e}")

    # -------- logging --------

    def _log(self, msg: str):
        if hasattr(self.ctx, "log"):
            try:
                self.ctx.log(msg)
                return
            except Exception:
                pass
        # fallback: status label
        self.status.setText(msg)
