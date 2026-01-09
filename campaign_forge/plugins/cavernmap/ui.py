# -------------------------
# ui.py
# -------------------------
from __future__ import annotations

from dataclasses import asdict
from typing import Optional, Dict, Any
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox,
    QLabel, QPushButton, QSpinBox, QCheckBox, QComboBox,
    QPlainTextEdit, QListWidget, QListWidgetItem, QMessageBox, QSplitter
)

from .generator import CavernParams, CavernResult, generate_cavern
from .exports import export_png, export_svg, export_key_md


def _grid_to_qimage(result: CavernResult, cell_px: int = 6, show_biome: bool = False) -> QImage:
    w = result.width * cell_px
    h = result.height * cell_px
    img = QImage(w, h, QImage.Format.Format_RGB32)
    img.fill(0x000000)

    biome_colors = {
        "Limestone": (0x80, 0x80, 0x80),
        "Fungal": (0x7a, 0x4f, 0x9a),
        "Crystal": (0x7b, 0xb6, 0xd6),
        "Flooded": (0x46, 0x6c, 0xb4),
        "Volcanic": (0xb3, 0x5a, 0x44),
        "Bonefield": (0xb0, 0xb0, 0x8a),
        "Slime": (0x5a, 0xa0, 0x5a),
        "Ruins": (0x9a, 0x7a, 0x5a),
    }

    def pack(rgb):
        r, g, b = rgb
        return (r << 16) | (g << 8) | b

    wall = pack((0x14, 0x14, 0x14))
    floor_plain = pack((0xb0, 0xb0, 0xb0))

    for y in range(result.height):
        for x in range(result.width):
            cell = result.grid[y][x]
            if cell == 0:
                col = wall
            else:
                if show_biome:
                    b = result.biome_grid[y][x]
                    rgb = biome_colors.get(b, (0xb0, 0xb0, 0xb0))
                    col = pack(rgb)
                else:
                    col = floor_plain

            x0 = x * cell_px
            y0 = y * cell_px
            for py in range(y0, y0 + cell_px):
                for px in range(x0, x0 + cell_px):
                    img.setPixel(px, py, col)

    return img


class CavernMapWidget(QWidget):
    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx
        self.plugin_id = "cavernmap"

        self.generate_count = 0
        self._last_result: Optional[CavernResult] = None
        self._show_biomes = True
        self._cell_px_preview = 6

        self._build_ui()

    # -------- UI --------

    def _build_ui(self):
        root = QVBoxLayout(self)

        top = QHBoxLayout()
        title = QLabel("<b>Cavern Generator</b> — Cellular Automata")
        top.addWidget(title)
        top.addStretch(1)

        self.btn_generate = QPushButton("Generate")
        self.btn_export = QPushButton("Export Session Pack")
        self.btn_export.setEnabled(False)

        top.addWidget(self.btn_generate)
        top.addWidget(self.btn_export)
        root.addLayout(top)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        root.addWidget(splitter, 1)

        # Left: controls
        controls = QWidget()
        controls_layout = QVBoxLayout(controls)

        grp = QGroupBox("Generation Controls")
        form = QFormLayout(grp)

        self.sp_w = QSpinBox(); self.sp_w.setRange(20, 400); self.sp_w.setValue(80)
        self.sp_h = QSpinBox(); self.sp_h.setRange(20, 400); self.sp_h.setValue(60)
        self.sp_fill = QSpinBox(); self.sp_fill.setRange(1, 99); self.sp_fill.setValue(48)
        self.sp_steps = QSpinBox(); self.sp_steps.setRange(1, 12); self.sp_steps.setValue(5)
        self.sp_birth = QSpinBox(); self.sp_birth.setRange(1, 8); self.sp_birth.setValue(5)
        self.sp_death = QSpinBox(); self.sp_death.setRange(0, 8); self.sp_death.setValue(3)

        self.chk_border = QCheckBox("Force border walls"); self.chk_border.setChecked(True)
        self.chk_keep_largest = QCheckBox("Keep largest connected cave"); self.chk_keep_largest.setChecked(True)

        self.sp_min_region = QSpinBox(); self.sp_min_region.setRange(0, 5000); self.sp_min_region.setValue(50)

        self.sp_widen = QSpinBox(); self.sp_widen.setRange(0, 10); self.sp_widen.setValue(0)
        self.chk_close_holes = QCheckBox("Close tiny holes"); self.chk_close_holes.setChecked(True)

        self.cmb_biomes = QComboBox()
        self.cmb_biomes.addItems(["simple", "none"])
        self.cmb_biomes.setCurrentText("simple")

        self.sp_biome_count = QSpinBox(); self.sp_biome_count.setRange(1, 8); self.sp_biome_count.setValue(4)

        self.chk_show_biomes = QCheckBox("Preview biomes"); self.chk_show_biomes.setChecked(True)

        form.addRow("Width", self.sp_w)
        form.addRow("Height", self.sp_h)
        form.addRow("Initial wall %", self.sp_fill)
        form.addRow("Smooth steps", self.sp_steps)
        form.addRow("Birth limit", self.sp_birth)
        form.addRow("Death limit", self.sp_death)
        form.addRow(self.chk_border)
        form.addRow(self.chk_keep_largest)
        form.addRow("Min floor region size", self.sp_min_region)
        form.addRow("Widen passes", self.sp_widen)
        form.addRow(self.chk_close_holes)
        form.addRow("Biome overlay", self.cmb_biomes)
        form.addRow("Biome seeds", self.sp_biome_count)
        form.addRow(self.chk_show_biomes)

        controls_layout.addWidget(grp)

        # Regions list + details
        grp_regions = QGroupBox("Regions")
        reg_layout = QVBoxLayout(grp_regions)
        self.lst_regions = QListWidget()
        self.txt_region = QPlainTextEdit()
        self.txt_region.setReadOnly(True)
        reg_layout.addWidget(self.lst_regions, 2)
        reg_layout.addWidget(self.txt_region, 1)
        controls_layout.addWidget(grp_regions, 2)

        # Log / stats
        grp_out = QGroupBox("Output")
        out_layout = QVBoxLayout(grp_out)
        self.txt_stats = QPlainTextEdit()
        self.txt_stats.setReadOnly(True)
        out_layout.addWidget(self.txt_stats)
        controls_layout.addWidget(grp_out, 1)

        splitter.addWidget(controls)

        # Right: preview
        preview = QWidget()
        pv_layout = QVBoxLayout(preview)
        self.lbl_preview = QLabel("Generate a cavern to preview.")
        self.lbl_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_preview.setMinimumSize(420, 320)
        self.lbl_preview.setStyleSheet("QLabel { background: #111; color: #ccc; border: 1px solid #333; }")
        pv_layout.addWidget(self.lbl_preview, 1)
        splitter.addWidget(preview)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        # Events
        self.btn_generate.clicked.connect(self.on_generate)
        self.btn_export.clicked.connect(self.on_export)
        self.lst_regions.currentItemChanged.connect(self.on_region_selected)
        self.chk_show_biomes.stateChanged.connect(self.on_refresh_preview)

    # -------- State --------

    def serialize_state(self) -> dict:
        return {
            "version": 1,
            "ui": {
                "w": self.sp_w.value(),
                "h": self.sp_h.value(),
                "fill": self.sp_fill.value(),
                "steps": self.sp_steps.value(),
                "birth": self.sp_birth.value(),
                "death": self.sp_death.value(),
                "border": self.chk_border.isChecked(),
                "keep_largest": self.chk_keep_largest.isChecked(),
                "min_region": self.sp_min_region.value(),
                "widen": self.sp_widen.value(),
                "close_holes": self.chk_close_holes.isChecked(),
                "biomes": self.cmb_biomes.currentText(),
                "biome_count": self.sp_biome_count.value(),
                "show_biomes": self.chk_show_biomes.isChecked(),
            },
            "data": {
                "generate_count": self.generate_count,
                "last_seed": (self._last_result.seed if self._last_result else None),
            }
        }

    def load_state(self, state: dict) -> None:
        if not state:
            return
        ver = state.get("version", 1)
        if ver != 1:
            self.ctx.log(f"[CavernMap] Unknown state version: {ver}")
            return
        ui = state.get("ui", {})
        self.sp_w.setValue(int(ui.get("w", 80)))
        self.sp_h.setValue(int(ui.get("h", 60)))
        self.sp_fill.setValue(int(ui.get("fill", 48)))
        self.sp_steps.setValue(int(ui.get("steps", 5)))
        self.sp_birth.setValue(int(ui.get("birth", 5)))
        self.sp_death.setValue(int(ui.get("death", 3)))
        self.chk_border.setChecked(bool(ui.get("border", True)))
        self.chk_keep_largest.setChecked(bool(ui.get("keep_largest", True)))
        self.sp_min_region.setValue(int(ui.get("min_region", 50)))
        self.sp_widen.setValue(int(ui.get("widen", 0)))
        self.chk_close_holes.setChecked(bool(ui.get("close_holes", True)))
        self.cmb_biomes.setCurrentText(str(ui.get("biomes", "simple")))
        self.sp_biome_count.setValue(int(ui.get("biome_count", 4)))
        self.chk_show_biomes.setChecked(bool(ui.get("show_biomes", True)))

        data = state.get("data", {})
        self.generate_count = int(data.get("generate_count", 0))

    # -------- Helpers --------

    def _gather_params(self) -> CavernParams:
        biomes = self.cmb_biomes.currentText()
        return CavernParams(
            width=self.sp_w.value(),
            height=self.sp_h.value(),
            fill_percent=self.sp_fill.value(),
            smooth_steps=self.sp_steps.value(),
            birth_limit=self.sp_birth.value(),
            death_limit=self.sp_death.value(),
            border_walls=self.chk_border.isChecked(),
            keep_largest_region=self.chk_keep_largest.isChecked(),
            min_region_size=self.sp_min_region.value(),
            widen_passes=self.sp_widen.value(),
            close_small_holes=self.chk_close_holes.isChecked(),
            biome_mode=("simple" if biomes == "simple" else "none"),
            biome_count=self.sp_biome_count.value(),
        )

    def _derive_rng(self, iteration: int):
        # Campaign Forge convention: ctx.derive_rng(master_seed, plugin_id, action, iteration)
        # If your ctx signature differs, adjust this in one place.
        return self.ctx.derive_rng(self.ctx.master_seed, self.plugin_id, "generate", iteration)

    def _render_preview(self):
        if not self._last_result:
            self.lbl_preview.setText("Generate a cavern to preview.")
            self.lbl_preview.setPixmap(QPixmap())
            self.btn_export.setEnabled(False)
            return

        show_biomes = self.chk_show_biomes.isChecked() and (self.cmb_biomes.currentText() == "simple")
        img = _grid_to_qimage(self._last_result, cell_px=self._cell_px_preview, show_biome=show_biomes)
        pm = QPixmap.fromImage(img)
        self.lbl_preview.setPixmap(pm)
        self.lbl_preview.setScaledContents(True)
        self.btn_export.setEnabled(True)

    def _refresh_regions_list(self):
        self.lst_regions.clear()
        if not self._last_result:
            return
        for r in self._last_result.regions:
            item = QListWidgetItem(f"R{r.id}: {r.name} ({r.kind}, {r.biome}, {r.size} cells)")
            item.setData(Qt.ItemDataRole.UserRole, r.id)
            self.lst_regions.addItem(item)
        if self._last_result.regions:
            self.lst_regions.setCurrentRow(0)

    def _update_stats_box(self):
        if not self._last_result:
            self.txt_stats.setPlainText("")
            return
        s = self._last_result.stats
        lines = []
        lines.append(f"Seed: {self._last_result.seed}")
        lines.append(f"Size: {int(s['width'])}×{int(s['height'])}")
        lines.append(f"Floor ratio: {s['floor_ratio']:.2%}")
        lines.append(f"Regions: {int(s['region_count'])}")
        lines.append(f"Largest region: {int(s['largest_region'])} cells")
        self.txt_stats.setPlainText("\n".join(lines))

    # -------- Slots --------

    def on_generate(self):
        try:
            params = self._gather_params()
            rng = self._derive_rng(self.generate_count)
            # Try to extract a stable seed integer for logging/exports
            # (If ctx.derive_rng returns a Random with unknown seed, we still keep master+iteration.)
            seed_used = getattr(rng, "seed_value", None)
            if seed_used is None:
                # Deterministic enough: combine master+iteration into a visible seed marker
                seed_used = int(self.ctx.master_seed) ^ (self.generate_count + 1) * 2654435761

            self._last_result = generate_cavern(params, rng=rng, seed_used=seed_used)
            self.generate_count += 1

            self.ctx.log(f"[CavernMap] Generated cavern {params.width}×{params.height} seed={self._last_result.seed} regions={len(self._last_result.regions)}")
            self._refresh_regions_list()
            self._update_stats_box()
            self._render_preview()

            # Send a useful summary to scratchpad
            md = self._build_scratchpad_summary()
            self.ctx.scratchpad_add(md, tags=["Cavern", "CavernMap", f"Seed:{self._last_result.seed}"])

        except Exception as e:
            self.ctx.log(f"[CavernMap] Generate failed: {e}")
            QMessageBox.critical(self, "Cavern Generator Error", str(e))

    def on_region_selected(self, cur: QListWidgetItem, prev: QListWidgetItem):
        if not self._last_result or not cur:
            self.txt_region.setPlainText("")
            return
        rid = cur.data(Qt.ItemDataRole.UserRole)
        reg = next((r for r in self._last_result.regions if r.id == rid), None)
        if not reg:
            self.txt_region.setPlainText("")
            return
        x0, y0, x1, y1 = reg.bbox
        text = []
        text.append(f"{reg.name}")
        text.append("")
        text.append(f"ID: R{reg.id}")
        text.append(f"Type: {reg.kind}")
        text.append(f"Biome: {reg.biome}")
        text.append(f"Cells: {reg.size}")
        text.append(f"BBox: ({x0},{y0})–({x1},{y1})")
        text.append(f"Exits (approx): {reg.exits}")
        text.append("")
        text.append("GM Prompts:")
        text.append("- Who claims this place?")
        text.append("- What would make it change?")
        text.append("- What secret does it hide?")
        self.txt_region.setPlainText("\n".join(text))

    def on_refresh_preview(self):
        self._render_preview()

    def on_export(self):
        if not self._last_result:
            return
        try:
            seed = self._last_result.seed
            pack_dir = self.ctx.export_manager.create_session_pack("cavernmap", seed=seed)
            pack_dir = Path(pack_dir)

            png_player = pack_dir / "cavern_map.png"
            png_biome = pack_dir / "cavern_map_biomes.png"
            svg_path = pack_dir / "cavern_map.svg"
            key_path = pack_dir / "cavern_key.md"

            export_png(self._last_result, png_player, cell_px=8, show_biome=False)
            if self.cmb_biomes.currentText() == "simple":
                export_png(self._last_result, png_biome, cell_px=8, show_biome=True)
            export_svg(self._last_result, svg_path, cell_px=10, show_biome=(self.cmb_biomes.currentText() == "simple"))
            export_key_md(self._last_result, key_path, title="Cavern Key")

            self.ctx.log(f"[CavernMap] Exported session pack: {pack_dir}")
            QMessageBox.information(self, "Export Complete", f"Exported session pack:\n{pack_dir}")

        except Exception as e:
            self.ctx.log(f"[CavernMap] Export failed: {e}")
            QMessageBox.critical(self, "Export Error", str(e))

    # -------- Content helpers --------

    def _build_scratchpad_summary(self) -> str:
        r = self._last_result
        if not r:
            return ""
        lines = []
        lines.append(f"# Cavern Generated (Seed {r.seed})")
        lines.append("")
        lines.append(f"- Size: **{r.width}×{r.height}**")
        lines.append(f"- Regions: **{len(r.regions)}**")
        lines.append(f"- Floor ratio: **{r.stats['floor_ratio']:.2%}**")
        lines.append("")
        lines.append("## Region Index")
        lines.append("")
        for reg in r.regions[:25]:
            lines.append(f"- **R{reg.id} {reg.name}** — {reg.kind}, {reg.biome}, {reg.size} cells (exits≈{reg.exits})")
        if len(r.regions) > 25:
            lines.append(f"- *(+{len(r.regions)-25} more regions)*")
        lines.append("")
        lines.append("## GM Hooks (quick sparks)")
        lines.append("")
        lines.append("- Something *moves* between regions when the party makes loud noise.")
        lines.append("- A ‘safe’ biome is actually a trap ecosystem cultivated by something intelligent.")
        lines.append("- One region is impossibly worked-stone beneath natural limestone — why?")
        return "\n".join(lines)