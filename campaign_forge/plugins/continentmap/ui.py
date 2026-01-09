from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Dict, Any, List

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QPushButton,
    QSpinBox, QDoubleSpinBox, QCheckBox, QGroupBox, QTextEdit, QComboBox,
    QSlider, QMessageBox, QScrollArea
)
from PySide6.QtCore import Qt

from .generator import generate_continent, ContinentModel, biome_name
from .renderer import render_base, render_factions_overlay, compose
from .preview_window import ContinentPreviewWindow
from .exports import export_session_pack


@dataclass
class _Settings:
    w: int = 256
    h: int = 192
    sea_level: float = 0.50
    ruggedness: float = 0.60
    coastline: float = 0.65
    moisture: float = 0.55
    temperature: float = 0.55
    river_density: float = 0.35
    add_islands: bool = True
    factions_n: int = 8
    contested_band: float = 0.20

    # View
    show_rivers: bool = True
    show_capitals: bool = True
    show_factions: bool = True
    show_borders: bool = True
    show_contested: bool = True
    overlay_opacity: float = 0.45


class ContinentMapWidget(QWidget):
    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx
        self._settings = _Settings()
        self._gen_iteration = 0
        self._last_seed = None  # type: Optional[int]

        self._model: Optional[ContinentModel] = None
        self._preview: Optional[ContinentPreviewWindow] = None

        self._build_ui()

    # ---------------- UI ----------------

    def _build_ui(self):
        outer = QVBoxLayout(self)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll, 1)

        container = QWidget()
        scroll.setWidget(container)

        root = QVBoxLayout(container)

        title = QLabel("<b>Continental Map Generator</b> — preview opens in a separate window.")
        title.setWordWrap(True)
        root.addWidget(title)

        top = QHBoxLayout()
        root.addLayout(top, 1)

        # Left: controls
        controls_col = QVBoxLayout()
        top.addLayout(controls_col, 1)

        gen_box = QGroupBox("Generation")
        gen_form = QFormLayout(gen_box)

        self.sp_w = QSpinBox(); self.sp_w.setRange(64, 512); self.sp_w.setValue(self._settings.w)
        self.sp_h = QSpinBox(); self.sp_h.setRange(64, 512); self.sp_h.setValue(self._settings.h)

        self.d_sea = QDoubleSpinBox(); self.d_sea.setRange(0.20, 0.80); self.d_sea.setSingleStep(0.01); self.d_sea.setValue(self._settings.sea_level)
        self.d_rug = QDoubleSpinBox(); self.d_rug.setRange(0.0, 1.0); self.d_rug.setSingleStep(0.05); self.d_rug.setValue(self._settings.ruggedness)
        self.d_coast = QDoubleSpinBox(); self.d_coast.setRange(0.0, 1.0); self.d_coast.setSingleStep(0.05); self.d_coast.setValue(self._settings.coastline)
        self.d_moist = QDoubleSpinBox(); self.d_moist.setRange(0.0, 1.0); self.d_moist.setSingleStep(0.05); self.d_moist.setValue(self._settings.moisture)
        self.d_temp = QDoubleSpinBox(); self.d_temp.setRange(0.0, 1.0); self.d_temp.setSingleStep(0.05); self.d_temp.setValue(self._settings.temperature)
        self.d_rivers = QDoubleSpinBox(); self.d_rivers.setRange(0.0, 1.0); self.d_rivers.setSingleStep(0.05); self.d_rivers.setValue(self._settings.river_density)

        self.chk_islands = QCheckBox("Add islands")
        self.chk_islands.setChecked(self._settings.add_islands)

        self.sp_factions = QSpinBox(); self.sp_factions.setRange(0, 24); self.sp_factions.setValue(self._settings.factions_n)
        self.d_contested = QDoubleSpinBox(); self.d_contested.setRange(0.05, 0.60); self.d_contested.setSingleStep(0.02); self.d_contested.setValue(self._settings.contested_band)

        gen_form.addRow("Width (cells)", self.sp_w)
        gen_form.addRow("Height (cells)", self.sp_h)
        gen_form.addRow("Sea level", self.d_sea)
        gen_form.addRow("Ruggedness", self.d_rug)
        gen_form.addRow("Coastline", self.d_coast)
        gen_form.addRow("Moisture", self.d_moist)
        gen_form.addRow("Temperature", self.d_temp)
        gen_form.addRow("River density", self.d_rivers)
        gen_form.addRow(self.chk_islands)
        gen_form.addRow("Factions", self.sp_factions)
        gen_form.addRow("Contested band", self.d_contested)
        controls_col.addWidget(gen_box)

        view_box = QGroupBox("View")
        view_form = QFormLayout(view_box)

        self.chk_show_rivers = QCheckBox("Rivers"); self.chk_show_rivers.setChecked(self._settings.show_rivers)
        self.chk_show_capitals = QCheckBox("Capitals"); self.chk_show_capitals.setChecked(self._settings.show_capitals)
        self.chk_show_factions = QCheckBox("Faction overlay"); self.chk_show_factions.setChecked(self._settings.show_factions)
        self.chk_show_borders = QCheckBox("Borders"); self.chk_show_borders.setChecked(self._settings.show_borders)
        self.chk_show_contested = QCheckBox("Contested shading"); self.chk_show_contested.setChecked(self._settings.show_contested)

        self.sl_opacity = QSlider(Qt.Orientation.Horizontal)
        self.sl_opacity.setRange(0, 100)
        self.sl_opacity.setValue(int(self._settings.overlay_opacity * 100))

        view_form.addRow(self.chk_show_rivers)
        view_form.addRow(self.chk_show_capitals)
        view_form.addRow(self.chk_show_factions)
        view_form.addRow(self.chk_show_borders)
        view_form.addRow(self.chk_show_contested)
        view_form.addRow("Overlay opacity", self.sl_opacity)
        controls_col.addWidget(view_box)

        btn_row = QHBoxLayout()
        self.btn_open_preview = QPushButton("Open Preview Window")
        self.btn_generate = QPushButton("Generate")
        self.btn_reroll = QPushButton("Reroll (new iteration)")
        btn_row.addWidget(self.btn_open_preview)
        btn_row.addWidget(self.btn_generate)
        btn_row.addWidget(self.btn_reroll)
        controls_col.addLayout(btn_row)

        btn_row2 = QHBoxLayout()
        self.btn_to_scratch = QPushButton("Send Summary to Scratchpad")
        self.btn_export = QPushButton("Export Session Pack")
        btn_row2.addWidget(self.btn_to_scratch)
        btn_row2.addWidget(self.btn_export)
        controls_col.addLayout(btn_row2)

        # Right: inspector (selection info)
        inspector_col = QVBoxLayout()
        top.addLayout(inspector_col, 1)

        inspector_col.addWidget(QLabel("<b>Inspector</b> (click a cell in the preview window)"))

        self.lbl_seed = QLabel("Seed: —")
        self.lbl_seed.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        inspector_col.addWidget(self.lbl_seed)

        self.txt_info = QTextEdit()
        self.txt_info.setReadOnly(True)
        self.txt_info.setPlaceholderText("Generate a map, open the preview, then click a location to inspect details.")
        inspector_col.addWidget(self.txt_info, 1)

        self.lbl_stats = QLabel("")
        self.lbl_stats.setWordWrap(True)
        inspector_col.addWidget(self.lbl_stats)

        # wiring
        self.btn_open_preview.clicked.connect(self._ensure_preview)
        self.btn_generate.clicked.connect(self._generate_same_iteration)
        self.btn_reroll.clicked.connect(self._generate_next_iteration)
        self.btn_export.clicked.connect(self._export)
        self.btn_to_scratch.clicked.connect(self._to_scratchpad)

        for w in [
            self.chk_show_rivers, self.chk_show_capitals, self.chk_show_factions,
            self.chk_show_borders, self.chk_show_contested
        ]:
            w.toggled.connect(self._refresh_preview)

        self.sl_opacity.valueChanged.connect(self._refresh_preview)

    # ---------------- Preview plumbing ----------------

    def _ensure_preview(self):
        if self._preview is None:
            self._preview = ContinentPreviewWindow(parent=None)
            self._preview.cell_clicked.connect(self._on_cell_clicked)
        self._preview.show()
        self._preview.raise_()
        self._preview.activateWindow()
        self._refresh_preview()

    def _render_current(self):
        if not self._model:
            return None, "No map yet."
        base = render_base(
            self._model,
            show_rivers=self.chk_show_rivers.isChecked(),
            show_capitals=self.chk_show_capitals.isChecked(),
        )
        overlay = None
        if self.chk_show_factions.isChecked():
            overlay = render_factions_overlay(
                self._model,
                opacity=self.sl_opacity.value() / 100.0,
                show_borders=self.chk_show_borders.isChecked(),
                show_contested=self.chk_show_contested.isChecked(),
            )
        img = compose(base, overlay)
        status = f"{self._model.w}×{self._model.h} cells — seed {self._model.seed} — factions {len(self._model.factions)}"
        return img, status

    def _refresh_preview(self):
        if not self._preview:
            return
        img, status = self._render_current()
        self._preview.set_image(img, self._model, status_text=status)

    # ---------------- Generation ----------------

    def _pull_settings_from_ui(self):
        self._settings.w = int(self.sp_w.value())
        self._settings.h = int(self.sp_h.value())
        self._settings.sea_level = float(self.d_sea.value())
        self._settings.ruggedness = float(self.d_rug.value())
        self._settings.coastline = float(self.d_coast.value())
        self._settings.moisture = float(self.d_moist.value())
        self._settings.temperature = float(self.d_temp.value())
        self._settings.river_density = float(self.d_rivers.value())
        self._settings.add_islands = bool(self.chk_islands.isChecked())
        self._settings.factions_n = int(self.sp_factions.value())
        self._settings.contested_band = float(self.d_contested.value())

    def _derive_seed(self) -> int:
        # stable across runs for this project, varies by iteration
        return self.ctx.derive_seed("continentmap", "generate", self._gen_iteration)

    def _generate_same_iteration(self):
        self._pull_settings_from_ui()
        seed = self._derive_seed()
        self._do_generate(seed)

    def _generate_next_iteration(self):
        self._gen_iteration += 1
        self._generate_same_iteration()

    def _do_generate(self, seed: int):
        try:
            self._model = generate_continent(
                seed=seed,
                w=self._settings.w,
                h=self._settings.h,
                sea_level=self._settings.sea_level,
                ruggedness=self._settings.ruggedness,
                coastline=self._settings.coastline,
                moisture=self._settings.moisture,
                temperature=self._settings.temperature,
                river_density=self._settings.river_density,
                add_islands=self._settings.add_islands,
                factions_n=self._settings.factions_n,
                contested_band=self._settings.contested_band,
            )
            self._last_seed = seed
            self.lbl_seed.setText(f"Seed: {seed} (iteration {self._gen_iteration})")
            self._update_stats()
            self.ctx.log(f"[continentmap] Generated {self._model.w}×{self._model.h} seed={seed} factions={len(self._model.factions)}")
            self._refresh_preview()
        except Exception as e:
            self.ctx.log(f"[continentmap] Generation failed: {e}")
            QMessageBox.warning(self, "Generation failed", str(e))

    def _update_stats(self):
        if not self._model:
            self.lbl_stats.setText("")
            return
        land_pct = self._model.notes.get("land_pct", 0.0) * 100.0
        self.lbl_stats.setText(
            f"Land coverage: {land_pct:.1f}% | "
            f"Biomes: {len(self._model.notes.get('biome_counts', {}))} | "
            f"Factions: {len(self._model.factions)}"
        )

    # ---------------- Inspector ----------------

    def _on_cell_clicked(self, x: int, y: int):
        if not self._model:
            return
        i = self._model.idx(x, y)
        e = self._model.elev[i]
        m = self._model.moist[i]
        t = self._model.temp[i]
        b = self._model.biome[i]
        is_land = self._model.land[i]
        has_river = self._model.river[i]
        fid = self._model.faction[i]
        cont = self._model.contested[i]

        lines = []
        lines.append(f"Cell: ({x}, {y})")
        lines.append(f"Land: {'yes' if is_land else 'no'}")
        lines.append(f"Elevation: {e:.3f}")
        lines.append(f"Moisture: {m:.3f}")
        lines.append(f"Temperature: {t:.3f}")
        lines.append(f"Biome: {biome_name(b)}")
        lines.append(f"River: {'yes' if has_river else 'no'}")

        if fid >= 0 and fid < len(self._model.factions):
            f = self._model.factions[fid]
            lines.append("")
            lines.append(f"Faction: {f.name} ({f.kind})")
            lines.append(f"Contested: {'yes' if cont else 'no'}")
            lines.append(f"Capital: {f.capital}")
        else:
            lines.append("")
            lines.append("Faction: —")

        self.txt_info.setPlainText("\n".join(lines))

    # ---------------- Export & Scratchpad ----------------

    def _export(self):
        if not self._model:
            QMessageBox.information(self, "Nothing to export", "Generate a map first.")
            return
        try:
            base = render_base(self._model, show_rivers=True, show_capitals=True)
            overlay = render_factions_overlay(self._model, opacity=0.45, show_borders=True, show_contested=True)
            combined = compose(base, overlay)

            pack = export_session_pack(
                self.ctx,
                self._model,
                images={
                    "continent_base.png": base,
                    "continent_factions.png": overlay,
                    "continent_combined.png": combined,
                }
            )
            self.ctx.log(f"[continentmap] Exported session pack: {pack}")
            QMessageBox.information(self, "Export complete", f"Exported to:\n{pack}")
        except Exception as e:
            self.ctx.log(f"[continentmap] Export failed: {e}")
            QMessageBox.warning(self, "Export failed", str(e))

    def _to_scratchpad(self):
        if not self._model:
            QMessageBox.information(self, "Nothing to send", "Generate a map first.")
            return
        try:
            f_lines = []
            f_lines.append(f"## Continent Map (seed {self._model.seed})")
            f_lines.append(f"- Size: {self._model.w}×{self._model.h}")
            f_lines.append(f"- Land: {self._model.notes.get('land_pct', 0.0)*100:.1f}%")
            f_lines.append("")
            f_lines.append("### Factions")
            if not self._model.factions:
                f_lines.append("_None_")
            else:
                for f in self._model.factions:
                    f_lines.append(f"- **{f.name}** ({f.kind}) — capital {f.capital}")
            text = "\n".join(f_lines)

            self.ctx.scratchpad_add(text, ["Map", "Continent", "Factions", "ContinentMap"])
            self.ctx.log("[continentmap] Sent summary to scratchpad.")
        except Exception as e:
            self.ctx.log(f"[continentmap] Scratchpad send failed: {e}")

    # ---------------- Persistence ----------------

    def serialize_state(self) -> Dict[str, Any]:
        # Keep it compact (don’t dump the full arrays)
        return {
            "version": 1,
            "state": {
                "settings": {
                    "w": self._settings.w,
                    "h": self._settings.h,
                    "sea_level": self._settings.sea_level,
                    "ruggedness": self._settings.ruggedness,
                    "coastline": self._settings.coastline,
                    "moisture": self._settings.moisture,
                    "temperature": self._settings.temperature,
                    "river_density": self._settings.river_density,
                    "add_islands": self._settings.add_islands,
                    "factions_n": self._settings.factions_n,
                    "contested_band": self._settings.contested_band,
                    "show_rivers": self.chk_show_rivers.isChecked(),
                    "show_capitals": self.chk_show_capitals.isChecked(),
                    "show_factions": self.chk_show_factions.isChecked(),
                    "show_borders": self.chk_show_borders.isChecked(),
                    "show_contested": self.chk_show_contested.isChecked(),
                    "overlay_opacity": self.sl_opacity.value() / 100.0,
                },
                "gen_iteration": self._gen_iteration,
                "last_seed": self._last_seed,
            }
        }

    def load_state(self, data: Dict[str, Any]) -> None:
        try:
            state = (data or {}).get("state", {})
            s = state.get("settings", {}) or {}

            # restore settings
            self._settings.w = int(s.get("w", self._settings.w))
            self._settings.h = int(s.get("h", self._settings.h))
            self._settings.sea_level = float(s.get("sea_level", self._settings.sea_level))
            self._settings.ruggedness = float(s.get("ruggedness", self._settings.ruggedness))
            self._settings.coastline = float(s.get("coastline", self._settings.coastline))
            self._settings.moisture = float(s.get("moisture", self._settings.moisture))
            self._settings.temperature = float(s.get("temperature", self._settings.temperature))
            self._settings.river_density = float(s.get("river_density", self._settings.river_density))
            self._settings.add_islands = bool(s.get("add_islands", self._settings.add_islands))
            self._settings.factions_n = int(s.get("factions_n", self._settings.factions_n))
            self._settings.contested_band = float(s.get("contested_band", self._settings.contested_band))

            # apply to widgets
            self.sp_w.setValue(self._settings.w)
            self.sp_h.setValue(self._settings.h)
            self.d_sea.setValue(self._settings.sea_level)
            self.d_rug.setValue(self._settings.ruggedness)
            self.d_coast.setValue(self._settings.coastline)
            self.d_moist.setValue(self._settings.moisture)
            self.d_temp.setValue(self._settings.temperature)
            self.d_rivers.setValue(self._settings.river_density)
            self.chk_islands.setChecked(self._settings.add_islands)
            self.sp_factions.setValue(self._settings.factions_n)
            self.d_contested.setValue(self._settings.contested_band)

            self.chk_show_rivers.setChecked(bool(s.get("show_rivers", True)))
            self.chk_show_capitals.setChecked(bool(s.get("show_capitals", True)))
            self.chk_show_factions.setChecked(bool(s.get("show_factions", True)))
            self.chk_show_borders.setChecked(bool(s.get("show_borders", True)))
            self.chk_show_contested.setChecked(bool(s.get("show_contested", True)))
            self.sl_opacity.setValue(int(float(s.get("overlay_opacity", 0.45)) * 100))

            self._gen_iteration = int(state.get("gen_iteration", 0))
            self._last_seed = state.get("last_seed", None)
            if self._last_seed is not None:
                self.lbl_seed.setText(f"Seed: {self._last_seed} (iteration {self._gen_iteration})")
        except Exception as e:
            self.ctx.log(f"[continentmap] Failed to load state: {e}")
