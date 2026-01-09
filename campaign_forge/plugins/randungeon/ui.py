from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSpinBox, QLineEdit, QTextEdit, QGroupBox, QCheckBox,
    QTabWidget, QComboBox, QMessageBox
)

from campaign_forge.plugins.dungeonmap.map_widget import DungeonMapView
from campaign_forge.plugins.dungeonmap.renderer import RenderConfig, render_dungeon_to_qimage
from campaign_forge.plugins.dungeonmap.svg_export import SvgConfig, dungeon_to_svg

from .generator import DungeonGenConfig, generate_dungeon, roll_exploration_table, GeneratedRoom


def dungeon_to_markdown(result) -> str:
    lines = []
    lines.append(f"# {result.title}")
    lines.append("")
    lines.append(f"**Seed:** `{result.seed}`  ")
    lines.append(f"**Rooms:** {len(result.rooms)}  ")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    by_type = result.summary.get("by_type", {})
    for k in sorted(by_type.keys()):
        lines.append(f"- **{k}**: {by_type[k]}")
    lines.append("")
    lines.append("## Room Key")
    lines.append("")
    for r in result.rooms:
        lines.append(f"### Room {r.index} (Depth {r.depth}) — {r.room_type}")
        lines.append(f"- **Geometry:** {r.geometry}")
        lines.append(f"- **Exits:** {', '.join(r.exits) if r.exits else 'None'}")
        lines.append(f"- **Contains:** {', '.join(r.contains) if r.contains else '—'}")
        if r.treasure_details:
            mult = f" ×{r.loot_multiplier}" if r.loot_multiplier != 1 else ""
            lines.append(f"- **Treasure{mult}:** {r.treasure_details}")
        if r.mods:
            lines.append(f"- **Mods ({len(r.mods)}):**")
            for m in r.mods:
                lines.append(f"  - {m}")
        if r.notes:
            lines.append("- **Notes:**")
            for n in r.notes:
                lines.append(f"  - {n}")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


class RandungeonWidget(QWidget):
    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx
        self._last_result = None

        # Map render config (shared with preview)
        self._render_cfg = RenderConfig(
            cell_size=10,
            margin=12,
            draw_grid=False,
            draw_axes=False,
            show_rooms=True,
            show_corridors=True,
            show_doors=True,
            show_secret_doors=True,
            show_labels=True,
            show_keys=False,
            show_traps=False,
            show_encounters=False,
            show_faction=False,
        )

        self.map_view = DungeonMapView(self.on_room_selected)
        self._last_dungeon = None

        self.tabs = QTabWidget()

        # -------- Generator tab --------
        gen_tab = QWidget()
        gen_root = QVBoxLayout(gen_tab)
        gen_root.setContentsMargins(8, 8, 8, 8)

        settings_box = QGroupBox("Dungeon Settings")
        s = QVBoxLayout(settings_box)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Title:"))
        self.title_edit = QLineEdit("The Infinite Corridor")
        row1.addWidget(self.title_edit, 1)
        s.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Seed:"))
        self.seed_spin = QSpinBox(); self.seed_spin.setRange(0, 2_000_000_000); self.seed_spin.setValue(1337)
        row2.addWidget(self.seed_spin)

        row2.addWidget(QLabel("Rooms:"))
        self.rooms_spin = QSpinBox(); self.rooms_spin.setRange(1, 300); self.rooms_spin.setValue(12)
        row2.addWidget(self.rooms_spin)

        row2.addWidget(QLabel("Start Depth:"))
        self.depth_spin = QSpinBox(); self.depth_spin.setRange(0, 999); self.depth_spin.setValue(0)
        row2.addWidget(self.depth_spin)
        row2.addStretch(1)
        s.addLayout(row2)

        # Map layout controls
        rowm = QHBoxLayout()
        rowm.addWidget(QLabel("Map W:"))
        self.map_w = QSpinBox(); self.map_w.setRange(40, 300); self.map_w.setValue(80)
        rowm.addWidget(self.map_w)
        rowm.addWidget(QLabel("Map H:"))
        self.map_h = QSpinBox(); self.map_h.setRange(30, 260); self.map_h.setValue(60)
        rowm.addWidget(self.map_h)
        rowm.addWidget(QLabel("Cell size:"))
        self.cell_size = QSpinBox(); self.cell_size.setRange(4, 28); self.cell_size.setValue(self._render_cfg.cell_size)
        rowm.addWidget(self.cell_size)
        self.cell_size.valueChanged.connect(self._on_render_changed)
        rowm.addStretch(1)
        s.addLayout(rowm)

        row3 = QHBoxLayout()
        row3.addWidget(QLabel("Corridor beats / room:"))
        self.beats_min = QSpinBox(); self.beats_min.setRange(0, 20); self.beats_min.setValue(1)
        self.beats_max = QSpinBox(); self.beats_max.setRange(0, 20); self.beats_max.setValue(4)
        row3.addWidget(QLabel("Min")); row3.addWidget(self.beats_min)
        row3.addWidget(QLabel("Max")); row3.addWidget(self.beats_max)

        self.special_passages_chk = QCheckBox("Allow special passage features")
        self.special_passages_chk.setChecked(True)
        row3.addWidget(self.special_passages_chk)
        row3.addStretch(1)
        s.addLayout(row3)

        gen_root.addWidget(settings_box)

        btns = QHBoxLayout()
        self.gen_btn = QPushButton("Generate Dungeon")
        self.gen_btn.clicked.connect(self.on_generate)
        btns.addWidget(self.gen_btn)

        self.export_btn = QPushButton("Export Session Pack")
        self.export_btn.setEnabled(False)
        self.export_btn.clicked.connect(self.on_export)
        btns.addWidget(self.export_btn)

        self.send_btn = QPushButton("Send to Scratchpad")
        self.send_btn.setEnabled(False)
        self.send_btn.clicked.connect(self.on_send)
        btns.addWidget(self.send_btn)

        btns.addStretch(1)
        gen_root.addLayout(btns)

        # Generator content tabs: map preview + keyed markdown
        self.gen_tabs = QTabWidget()

        map_tab = QWidget()
        map_root = QVBoxLayout(map_tab)
        map_root.setContentsMargins(0, 0, 0, 0)
        map_root.addWidget(self.map_view, 1)

        map_btns = QHBoxLayout()
        self.fit_btn = QPushButton("Fit")
        self.fit_btn.clicked.connect(lambda: self.map_view.fit_to_bounds())
        map_btns.addWidget(self.fit_btn)

        self.export_png_btn = QPushButton("Export PNG")
        self.export_png_btn.setEnabled(False)
        self.export_png_btn.clicked.connect(self.on_export_png)
        map_btns.addWidget(self.export_png_btn)

        self.export_svg_btn = QPushButton("Export SVG")
        self.export_svg_btn.setEnabled(False)
        self.export_svg_btn.clicked.connect(self.on_export_svg)
        map_btns.addWidget(self.export_svg_btn)

        map_btns.addStretch(1)
        map_root.addLayout(map_btns)

        key_tab = QWidget()
        key_root = QVBoxLayout(key_tab)
        key_root.setContentsMargins(0, 0, 0, 0)
        self.output = QTextEdit()
        self.output.setPlaceholderText("Dungeon markdown will appear here…")
        self.output.setLineWrapMode(QTextEdit.NoWrap)
        key_root.addWidget(self.output, 1)

        sel_tab = QWidget()
        sel_root = QVBoxLayout(sel_tab)
        sel_root.setContentsMargins(0, 0, 0, 0)
        self.selected = QTextEdit()
        self.selected.setReadOnly(True)
        self.selected.setPlaceholderText("Click a room in the map to see its details here…")
        sel_root.addWidget(self.selected, 1)

        self.gen_tabs.addTab(map_tab, "Map")
        self.gen_tabs.addTab(key_tab, "Room Key")
        self.gen_tabs.addTab(sel_tab, "Selected Room")
        gen_root.addWidget(self.gen_tabs, 1)

        # -------- Tables tab --------
        tables_tab = QWidget()
        troot = QVBoxLayout(tables_tab)
        troot.setContentsMargins(8, 8, 8, 8)

        tbox = QGroupBox("Exploration Tables (The Infinite Dungeon vibe)")
        tlay = QVBoxLayout(tbox)

        rowt = QHBoxLayout()
        rowt.addWidget(QLabel("Table:"))
        self.table_combo = QComboBox()
        self.table_combo.addItems([
            "Wandering Omen (d20)",
            "Dungeon Sound (d20)",
            "Dungeon Smell (d20)",
            "Door Quirk (d20)",
            "Trap Tell (d20)",
            "Weird Treasure Tag (d20)",
            "Faction Sign (d20)",
            "Wandering Monster Mood (d20)",
            "Room Dressing (d100; 61–100 roll twice)",
            "Exploration Complication (d100; 61–100 roll twice)",
            "Dungeon Boon (d100; 61–100 roll twice)",
        ])
        rowt.addWidget(self.table_combo, 1)

        rowt.addWidget(QLabel("Seed:"))
        self.table_seed = QSpinBox(); self.table_seed.setRange(0, 2_000_000_000); self.table_seed.setValue(1337)
        rowt.addWidget(self.table_seed)

        self.roll_btn = QPushButton("Roll")
        self.roll_btn.clicked.connect(self.on_roll_table)
        rowt.addWidget(self.roll_btn)

        rowt.addStretch(1)
        tlay.addLayout(rowt)

        self.table_out = QTextEdit()
        self.table_out.setPlaceholderText("Roll results will appear here…")
        self.table_out.setLineWrapMode(QTextEdit.WidgetWidth)
        tlay.addWidget(self.table_out, 1)

        troot.addWidget(tbox, 1)

        # Assemble tabs
        self.tabs.addTab(gen_tab, "Generator")
        self.tabs.addTab(tables_tab, "Exploration Tables")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(self.tabs)

    # -----------------
    # Render controls
    # -----------------

    def _on_render_changed(self, *_args):
        self._render_cfg.cell_size = int(self.cell_size.value())
        self.map_view.set_render_config(self._render_cfg)

    # -----------------
    # Actions
    # -----------------

    def on_generate(self):
        mn = int(self.beats_min.value())
        mx = int(self.beats_max.value())
        if mx < mn:
            mx = mn
            self.beats_max.setValue(mx)

        seed = int(self.seed_spin.value())
        rng = self.ctx.derive_rng(self.ctx.master_seed, "randungeon", "generate", seed)

        cfg = DungeonGenConfig(
            title=self.title_edit.text().strip() or "The Infinite Corridor",
            rooms=int(self.rooms_spin.value()),
            start_depth=int(self.depth_spin.value()),
            seed=seed,
            corridor_beats_min=mn,
            corridor_beats_max=mx,
            allow_special_passages=bool(self.special_passages_chk.isChecked()),
            map_width=int(self.map_w.value()),
            map_height=int(self.map_h.value()),
        )

        result = generate_dungeon(cfg, rng)
        self._last_result = result
        self._last_dungeon = result.map_dungeon

        md = dungeon_to_markdown(result)
        self.output.setPlainText(md)
        self.export_btn.setEnabled(True)
        self.send_btn.setEnabled(True)

        # Update map preview
        self._render_cfg.cell_size = int(self.cell_size.value())
        self.map_view.set_render_config(self._render_cfg)
        self.map_view.set_dungeon(self._last_dungeon, self._render_cfg)
        has_map = self._last_dungeon is not None
        for b in (self.fit_btn, self.export_png_btn, self.export_svg_btn):
            b.setEnabled(has_map)
        if has_map:
            self.map_view.fit_to_bounds()
            self.gen_tabs.setCurrentIndex(0)  # Map tab

        self.ctx.log(f"[Randungeon] Generated '{result.title}' — {len(result.rooms)} rooms (seed {seed}).")

    def on_room_selected(self, room) -> None:
        # room is a dungeonmap Room
        if not room:
            self.selected.setPlainText("")
            self.map_view.set_selected_room(None)
            return

        self.map_view.set_selected_room(room)
        if not self._last_result:
            self.selected.setPlainText(f"Room {room.id}")
            return

        meta: Optional[GeneratedRoom] = next((r for r in self._last_result.rooms if r.index == room.id), None)
        if not meta:
            self.selected.setPlainText(f"Room {room.id}")
            return

        # Compact per-room markdown
        lines = [
            f"### Room {meta.index} (Depth {meta.depth}) — {meta.room_type}",
            f"- Geometry: {meta.geometry}",
            f"- Exits: {', '.join(meta.exits) if meta.exits else 'None'}",
            f"- Contains: {', '.join(meta.contains) if meta.contains else '—'}",
        ]
        if meta.treasure_details:
            mult = f" ×{meta.loot_multiplier}" if meta.loot_multiplier != 1 else ""
            lines.append(f"- Treasure{mult}: {meta.treasure_details}")
        if meta.mods:
            lines.append(f"- Mods ({len(meta.mods)}):")
            for m in meta.mods[:8]:
                lines.append(f"  - {m}")
            if len(meta.mods) > 8:
                lines.append(f"  - …(+{len(meta.mods)-8} more)")
        if meta.notes:
            lines.append("- Notes:")
            for n in meta.notes[:10]:
                lines.append(f"  - {n}")
            if len(meta.notes) > 10:
                lines.append(f"  - …(+{len(meta.notes)-10} more)")

        self.selected.setPlainText("\n".join(lines))

    def on_export(self):
        if not self._last_result:
            return
        try:
            pack_dir = self.ctx.export_manager.create_session_pack("randungeon", seed=self._last_result.seed)
            md = self.output.toPlainText()
            p_md = self.ctx.export_manager.write_markdown(pack_dir, "dungeon.md", md)

            # If we have a map, export it into the pack as PNG + SVG
            if self._last_dungeon is not None:
                img = render_dungeon_to_qimage(self._last_dungeon, self._render_cfg)
                png_path = str(pack_dir / "map.png")
                img.save(png_path)

                svg_path = str(pack_dir / "map.svg")
                svg = dungeon_to_svg(self._last_dungeon, SvgConfig(cell_size=self._render_cfg.cell_size, margin=self._render_cfg.margin))
                with open(svg_path, "w", encoding="utf-8") as f:
                    f.write(svg)

                self.ctx.log(f"[Randungeon] Wrote: {png_path}")
                self.ctx.log(f"[Randungeon] Wrote: {svg_path}")

            self.ctx.log(f"[Randungeon] Exported session pack: {pack_dir}")
            self.ctx.log(f"[Randungeon] Wrote: {p_md}")
        except Exception as e:
            self.ctx.log(f"[Randungeon] Export failed: {e}")
            QMessageBox.warning(self, "Export failed", str(e))

    def on_export_png(self):
        if self._last_dungeon is None:
            return
        try:
            pack_dir = self.ctx.export_manager.create_session_pack("randungeon_map", seed=self._last_result.seed if self._last_result else None)
            img = render_dungeon_to_qimage(self._last_dungeon, self._render_cfg)
            png_path = str(pack_dir / "map.png")
            img.save(png_path)
            self.ctx.log(f"[Randungeon] Exported PNG: {png_path}")
        except Exception as e:
            self.ctx.log(f"[Randungeon] PNG export failed: {e}")
            QMessageBox.warning(self, "PNG export failed", str(e))

    def on_export_svg(self):
        if self._last_dungeon is None:
            return
        try:
            pack_dir = self.ctx.export_manager.create_session_pack("randungeon_map", seed=self._last_result.seed if self._last_result else None)
            svg_path = str(pack_dir / "map.svg")
            svg = dungeon_to_svg(self._last_dungeon, SvgConfig(cell_size=self._render_cfg.cell_size, margin=self._render_cfg.margin))
            with open(svg_path, "w", encoding="utf-8") as f:
                f.write(svg)
            self.ctx.log(f"[Randungeon] Exported SVG: {svg_path}")
        except Exception as e:
            self.ctx.log(f"[Randungeon] SVG export failed: {e}")
            QMessageBox.warning(self, "SVG export failed", str(e))

    def on_send(self):
        if not self._last_result:
            return
        md = self.output.toPlainText()
        tags = ["Dungeon", "Randungeon", f"Dungeon:{self._last_result.title}"]
        self.ctx.scratchpad_add(md, tags=tags)
        self.ctx.log(f"[Randungeon] Sent to scratchpad with tags: {', '.join(tags)}")

    def on_roll_table(self):
        seed = int(self.table_seed.value())
        rng = self.ctx.derive_rng(self.ctx.master_seed, "randungeon", "tables", seed, self.table_combo.currentText())
        tr = roll_exploration_table(rng, self.table_combo.currentText())
        self.table_out.append(f"[{tr.name}] Roll {tr.roll}: {tr.text}\n")

    # -----------------
    # Persistence hooks
    # -----------------

    def serialize_state(self) -> dict:
        return {
            "version": 3,
            "ui": {
                "title": self.title_edit.text(),
                "seed": int(self.seed_spin.value()),
                "rooms": int(self.rooms_spin.value()),
                "start_depth": int(self.depth_spin.value()),
                "map_w": int(self.map_w.value()),
                "map_h": int(self.map_h.value()),
                "cell_size": int(self.cell_size.value()),
                "beats_min": int(self.beats_min.value()),
                "beats_max": int(self.beats_max.value()),
                "special_passages": bool(self.special_passages_chk.isChecked()),
                "table_seed": int(self.table_seed.value()),
                "table_name": self.table_combo.currentText(),
            },
            "data": {
                "last_markdown": self.output.toPlainText(),
                "last_table_log": self.table_out.toPlainText(),
            }
        }

    def load_state(self, state: dict) -> None:
        if not state:
            return

        ver = int(state.get("version", 1))
        ui = state.get("ui", {})

        self.title_edit.setText(ui.get("title", "The Infinite Corridor"))
        self.seed_spin.setValue(int(ui.get("seed", 1337)))
        self.rooms_spin.setValue(int(ui.get("rooms", 12)))
        self.depth_spin.setValue(int(ui.get("start_depth", 0)))
        self.map_w.setValue(int(ui.get("map_w", 80)))
        self.map_h.setValue(int(ui.get("map_h", 60)))
        self.cell_size.setValue(int(ui.get("cell_size", self._render_cfg.cell_size)))
        self.beats_min.setValue(int(ui.get("beats_min", 1)))
        self.beats_max.setValue(int(ui.get("beats_max", 4)))
        self.special_passages_chk.setChecked(bool(ui.get("special_passages", True)))

        self.table_seed.setValue(int(ui.get("table_seed", 1337)))
        name = ui.get("table_name", "Wandering Omen (d20)")
        idx = self.table_combo.findText(name)
        if idx >= 0:
            self.table_combo.setCurrentIndex(idx)

        # Keep preview config in sync with controls (if a map exists)
        self._render_cfg.cell_size = int(self.cell_size.value())
        self.map_view.set_render_config(self._render_cfg)

        data = state.get("data", {})
        last_md = data.get("last_markdown", "")
        if last_md:
            self.output.setPlainText(last_md)
            self.export_btn.setEnabled(True)
            self.send_btn.setEnabled(True)

        last_log = data.get("last_table_log", "")
        if last_log:
            self.table_out.setPlainText(last_log)

        # v1/v2 states don't persist the dungeon geometry; user can regenerate for map.
        if ver < 2:
            self.ctx.log("[Randungeon] Loaded v1 state (regenerate to see map preview).")
