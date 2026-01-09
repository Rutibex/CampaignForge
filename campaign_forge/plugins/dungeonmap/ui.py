from __future__ import annotations

from typing import Optional, Dict, Any

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSpinBox, QDoubleSpinBox, QCheckBox, QTextEdit, QGroupBox,
    QApplication, QFileDialog, QTabWidget
)
from PySide6.QtCore import Qt

from .generator import (
    DungeonGenConfig, generate_dungeon,
    dungeon_room_key, dungeon_contents_text, Room, Dungeon
)
from .renderer import RenderConfig, render_dungeon_to_qimage
from .svg_export import SvgConfig, dungeon_to_svg
from .map_widget import DungeonMapView
from .edit_dialog import RoomEditDialog
from .preview_window import DungeonPreviewWindow


class DungeonMapWidget(QWidget):
    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx

        self._dungeon: Optional[Dungeon] = None
        self._selected_room: Optional[Room] = None

        # Render config (shared with preview)
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

        # Shared map view (reparented into preview window)
        self.map_view = DungeonMapView(self.on_room_selected)

        self._preview: Optional[DungeonPreviewWindow] = None
        self._preview_detached: bool = True
        self._preview_state: dict = {}

        self._build_ui()

    # ---------------- UI ----------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)

        # Settings box
        box = QGroupBox("Dungeon Settings")
        b = QVBoxLayout(box)

        self.seed = QSpinBox(); self.seed.setRange(0, 2_000_000_000); self.seed.setValue(1337)
        self.w = QSpinBox(); self.w.setRange(30, 240); self.w.setValue(80)
        self.h = QSpinBox(); self.h.setRange(30, 240); self.h.setValue(60)
        self.danger = QSpinBox(); self.danger.setRange(1, 10); self.danger.setValue(3)

        r1 = QHBoxLayout()
        r1.addWidget(QLabel("Seed:")); r1.addWidget(self.seed)
        r1.addWidget(QLabel("W:")); r1.addWidget(self.w)
        r1.addWidget(QLabel("H:")); r1.addWidget(self.h)
        r1.addWidget(QLabel("Danger:")); r1.addWidget(self.danger)
        r1.addStretch(1)
        b.addLayout(r1)

        self.max_rooms = QSpinBox(); self.max_rooms.setRange(1, 120); self.max_rooms.setValue(18)
        self.room_attempts = QSpinBox(); self.room_attempts.setRange(10, 4000); self.room_attempts.setValue(140)
        self.min_room = QSpinBox(); self.min_room.setRange(3, 40); self.min_room.setValue(5)
        self.max_room = QSpinBox(); self.max_room.setRange(3, 60); self.max_room.setValue(14)

        r2 = QHBoxLayout()
        r2.addWidget(QLabel("Max rooms:")); r2.addWidget(self.max_rooms)
        r2.addWidget(QLabel("Attempts:")); r2.addWidget(self.room_attempts)
        r2.addWidget(QLabel("Min room:")); r2.addWidget(self.min_room)
        r2.addWidget(QLabel("Max room:")); r2.addWidget(self.max_room)
        r2.addStretch(1)
        b.addLayout(r2)

        self.corridor_width = QSpinBox(); self.corridor_width.setRange(1, 5); self.corridor_width.setValue(1)
        self.straightness = QDoubleSpinBox(); self.straightness.setRange(0.0, 1.0); self.straightness.setSingleStep(0.1); self.straightness.setValue(0.65)
        self.corridor_density = QDoubleSpinBox(); self.corridor_density.setRange(0.0, 1.0); self.corridor_density.setSingleStep(0.05); self.corridor_density.setValue(0.35)
        self.dead_end_prune = QDoubleSpinBox(); self.dead_end_prune.setRange(0.0, 1.0); self.dead_end_prune.setSingleStep(0.05); self.dead_end_prune.setValue(0.25)

        r3 = QHBoxLayout()
        r3.addWidget(QLabel("Corridor width:")); r3.addWidget(self.corridor_width)
        r3.addWidget(QLabel("Straightness:")); r3.addWidget(self.straightness)
        r3.addWidget(QLabel("Corridor density:")); r3.addWidget(self.corridor_density)
        r3.addWidget(QLabel("Dead-end prune:")); r3.addWidget(self.dead_end_prune)
        r3.addStretch(1)
        b.addLayout(r3)

        self.cave_mode = QCheckBox("Cave mode")
        self.secret_doors = QSpinBox(); self.secret_doors.setRange(0, 50); self.secret_doors.setValue(2)
        self.secret_corridors = QSpinBox(); self.secret_corridors.setRange(0, 20); self.secret_corridors.setValue(1)

        r4 = QHBoxLayout()
        r4.addWidget(self.cave_mode)
        r4.addWidget(QLabel("Secret doors:")); r4.addWidget(self.secret_doors)
        r4.addWidget(QLabel("Secret corridors:")); r4.addWidget(self.secret_corridors)
        r4.addStretch(1)
        b.addLayout(r4)

        # Render / preview settings (kept minimal in main UI)
        self.cell_size = QSpinBox(); self.cell_size.setRange(4, 28); self.cell_size.setValue(self._render_cfg.cell_size)

        r5 = QHBoxLayout()
        r5.addWidget(QLabel("Cell size:")); r5.addWidget(self.cell_size)
        r5.addStretch(1)
        b.addLayout(r5)

        # Buttons row
        btns = QHBoxLayout()
        self.generate_btn = QPushButton("Generate")
        self.open_preview_btn = QPushButton("Open Preview")
        self.open_preview_btn.setToolTip("Open the map preview in its own window.")

        self.copy_key_btn = QPushButton("Copy Key"); self.copy_key_btn.setEnabled(False)
        self.copy_contents_btn = QPushButton("Copy Contents"); self.copy_contents_btn.setEnabled(False)
        self.send_scratch_btn = QPushButton("Send to Scratchpad"); self.send_scratch_btn.setEnabled(False)
        self.export_png_btn = QPushButton("Export PNG"); self.export_png_btn.setEnabled(False)
        self.export_svg_btn = QPushButton("Export SVG"); self.export_svg_btn.setEnabled(False)
        self.edit_room_btn = QPushButton("Edit Selected Room"); self.edit_room_btn.setEnabled(False)

        for w in [
            self.generate_btn, self.open_preview_btn, self.copy_key_btn, self.copy_contents_btn,
            self.send_scratch_btn, self.export_png_btn, self.export_svg_btn, self.edit_room_btn
        ]:
            btns.addWidget(w)
        btns.addStretch(1)
        b.addLayout(btns)

        root.addWidget(box)

        # Tabs (main content)
        self.tabs = QTabWidget()
        self.key_view = QTextEdit(); self.key_view.setReadOnly(True)
        self.contents_view = QTextEdit(); self.contents_view.setReadOnly(True)
        self.selected_view = QTextEdit(); self.selected_view.setReadOnly(True)
        self.selected_view.setPlaceholderText("Open Preview and click a room to view details.")

        self.tabs.addTab(self.key_view, "Room Key")
        self.tabs.addTab(self.contents_view, "Contents")
        self.tabs.addTab(self.selected_view, "Selected Room")

        root.addWidget(self.tabs, stretch=1)

        # Signals
        self.generate_btn.clicked.connect(self.on_generate)
        self.open_preview_btn.clicked.connect(self.on_open_preview)

        self.copy_key_btn.clicked.connect(self.on_copy_key)
        self.copy_contents_btn.clicked.connect(self.on_copy_contents)
        self.send_scratch_btn.clicked.connect(self.on_send_scratchpad)
        self.export_png_btn.clicked.connect(self.on_export_png)
        self.export_svg_btn.clicked.connect(self.on_export_svg)
        self.edit_room_btn.clicked.connect(self.on_edit_selected)

        self.cell_size.valueChanged.connect(self._on_cell_size_changed)

    # ---------------- Preview window management ----------------

    def _get_render_cfg(self) -> RenderConfig:
        return self._render_cfg

    def _set_render_cfg(self, cfg: RenderConfig) -> None:
        self._render_cfg = cfg
        self.map_view.set_render_config(self._render_cfg)

    def _ensure_preview(self) -> DungeonPreviewWindow:
        if self._preview is None:
            self._preview = DungeonPreviewWindow(
                map_view=self.map_view,
                get_render_config=self._get_render_cfg,
                set_render_config=self._set_render_cfg,
                on_request_dock_back=self.on_dock_preview_back,
                parent=None
            )
            # Apply persisted window state (if any)
            self._preview.apply_window_state(self._preview_state or {})
        return self._preview

    def on_open_preview(self) -> None:
        win = self._ensure_preview()
        win.show()
        win.raise_()
        win.activateWindow()
        self._preview_detached = True

    def on_dock_preview_back(self) -> None:
        # "Dock back" is implemented as: keep the window open but let the user close it
        # For now, just close the window (map stays functional when reopened).
        if self._preview:
            self._preview_state = self._preview.export_window_state()
            self._preview.close()
        self._preview_detached = False

    # ---------------- Generation ----------------

    def _on_cell_size_changed(self, v: int) -> None:
        self._render_cfg.cell_size = int(v)
        self.map_view.set_render_config(self._render_cfg)

    def on_generate(self) -> None:
        if self.max_room.value() < self.min_room.value():
            self.max_room.setValue(self.min_room.value())

        cfg = DungeonGenConfig(
            width=self.w.value(),
            height=self.h.value(),
            room_attempts=self.room_attempts.value(),
            room_min_size=self.min_room.value(),
            room_max_size=self.max_room.value(),
            max_rooms=self.max_rooms.value(),
            corridor_width=self.corridor_width.value(),
            straightness=float(self.straightness.value()),
            corridor_density=float(self.corridor_density.value()),
            dead_end_prune=float(self.dead_end_prune.value()),
            cave_mode=bool(self.cave_mode.isChecked()),
            secret_doors=int(self.secret_doors.value()),
            secret_corridors=int(self.secret_corridors.value()),
            danger=int(self.danger.value()),
            seed=int(self.seed.value())
        )

        d = generate_dungeon(cfg)
        self._dungeon = d
        self._selected_room = None

        self.map_view.set_dungeon(self._dungeon, self._render_cfg)
        self.map_view.reset_view()

        # Update text tabs
        self.key_view.setPlainText(dungeon_room_key(d))
        self.contents_view.setPlainText(dungeon_contents_text(d))

        self.selected_view.setPlainText("Click a room in the Preview window to see details.")

        # Enable actions
        self.copy_key_btn.setEnabled(True)
        self.copy_contents_btn.setEnabled(True)
        self.send_scratch_btn.setEnabled(True)
        self.export_png_btn.setEnabled(True)
        self.export_svg_btn.setEnabled(True)
        self.edit_room_btn.setEnabled(False)

        self.ctx.log(
            f"[DungeonMap] Generated rooms={len(d.rooms)} doors={len(d.doors)} corridors={len(d.corridors)} seed={cfg.seed}"
        )

        # Auto-open preview if not already visible
        self.on_open_preview()

    def on_room_selected(self, room: Optional[Room]) -> None:
        self._selected_room = room
        self.map_view.set_selected_room(room)

        if not room:
            self.selected_view.setPlainText("No room selected.")
            self.edit_room_btn.setEnabled(False)
            return

        self.edit_room_btn.setEnabled(True)

        # Build a readable room summary
        lines = []
        title = room.name.strip() if room.name else f"Room {room.id:02d}"
        lines.append(f"# {title}")
        lines.append(f"Tag: {room.tag}")
        if room.function: lines.append(f"Function: {room.function}")
        if room.condition: lines.append(f"Condition: {room.condition}")
        if room.occupancy: lines.append(f"Occupancy: {room.occupancy}")
        if room.control: lines.append(f"Control: {room.control}")
        if room.locked: lines.append(f"Locked: {room.lock_type or '(unspecified)'}")
        if room.description: lines.append("\n## Description\n" + room.description)
        if room.gm_notes: lines.append("\n## GM Notes\n" + room.gm_notes)

        c = room.contents
        if c.encounter: lines.append("\n## Encounter\n" + c.encounter)
        if c.trap: lines.append("\n## Trap\n" + c.trap)
        if c.treasure: lines.append("\n## Treasure\n" + c.treasure)
        if c.notes: lines.append("\n## Notes\n" + c.notes)

        self.selected_view.setPlainText("\n".join(lines).rstrip())

    def on_edit_selected(self) -> None:
        if not self._selected_room:
            return
        dlg = RoomEditDialog(self._selected_room, parent=self)
        if dlg.exec():
            dlg.apply_to_room()
            # refresh views
            if self._dungeon:
                self.key_view.setPlainText(dungeon_room_key(self._dungeon.rooms))
                self.contents_view.setPlainText(dungeon_contents_text(self._dungeon.rooms))
                self.map_view.set_dungeon(self._dungeon, self._render_cfg)
                self.on_room_selected(self._selected_room)

    # ---------------- Actions ----------------

    def on_copy_key(self) -> None:
        txt = self.key_view.toPlainText()
        QApplication.clipboard().setText(txt)
        self.ctx.log("[DungeonMap] Copied room key to clipboard.")

    def on_copy_contents(self) -> None:
        txt = self.contents_view.toPlainText()
        QApplication.clipboard().setText(txt)
        self.ctx.log("[DungeonMap] Copied contents to clipboard.")

    def on_send_scratchpad(self) -> None:
        if not self._dungeon:
            return
        text = "# Dungeon Room Key\n\n" + self.key_view.toPlainText() + "\n\n# Contents\n\n" + self.contents_view.toPlainText()
        self.ctx.scratchpad_add(text=text, tags=["Dungeon", "DungeonMap"])
        self.ctx.log("[DungeonMap] Sent dungeon key + contents to scratchpad.")

    def on_export_png(self) -> None:
        if not self._dungeon:
            return

        img = render_dungeon_to_qimage(self._dungeon, self._render_cfg)

        default_dir = self.ctx.project_dir / "exports"
        default_dir.mkdir(parents=True, exist_ok=True)

        path, _ = QFileDialog.getSaveFileName(
            self, "Export Dungeon Map (PNG)",
            str(default_dir / "dungeon_map.png"),
            "PNG Images (*.png)"
        )
        if not path:
            return
        ok = img.save(path, "PNG")
        self.ctx.log(f"[DungeonMap] Export PNG {'OK' if ok else 'FAILED'}: {path}")

    def on_export_svg(self) -> None:
        if not self._dungeon:
            return

        cfg = SvgConfig(cell_size=int(self._render_cfg.cell_size), margin=int(self._render_cfg.margin), draw_room_ids=True)
        svg_text = dungeon_to_svg(self._dungeon, cfg)

        default_dir = self.ctx.project_dir / "exports"
        default_dir.mkdir(parents=True, exist_ok=True)

        path, _ = QFileDialog.getSaveFileName(
            self, "Export Dungeon Map (SVG)",
            str(default_dir / "dungeon_map.svg"),
            "SVG Files (*.svg)"
        )
        if not path:
            return

        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(svg_text)
            self.ctx.log(f"[DungeonMap] Export SVG OK: {path}")
        except Exception as e:
            self.ctx.log(f"[DungeonMap] Export SVG FAILED: {path} ({e})")

    # ---------------- Persistence ----------------

    def serialize_state(self) -> dict:
        # Persist config + preview window state per project
        state = {
            "w": int(self.w.value()),
            "h": int(self.h.value()),
            "seed": int(self.seed.value()),
            "max_rooms": int(self.max_rooms.value()),
            "room_attempts": int(self.room_attempts.value()),
            "min_room": int(self.min_room.value()),
            "max_room": int(self.max_room.value()),
            "corridor_width": int(self.corridor_width.value()),
            "straightness": float(self.straightness.value()),
            "corridor_density": float(self.corridor_density.value()),
            "dead_end_prune": float(self.dead_end_prune.value()),
            "cave_mode": bool(self.cave_mode.isChecked()),
            "secret_doors": int(self.secret_doors.value()),
            "secret_corridors": int(self.secret_corridors.value()),
            "danger": int(self.danger.value()),
            "cell_size": int(self.cell_size.value()),

            "render_cfg": {
                "draw_grid": bool(self._render_cfg.draw_grid),
                "draw_axes": bool(getattr(self._render_cfg, "draw_axes", False)),
                "show_rooms": bool(getattr(self._render_cfg, "show_rooms", True)),
                "show_corridors": bool(getattr(self._render_cfg, "show_corridors", True)),
                "show_doors": bool(getattr(self._render_cfg, "show_doors", True)),
                "show_secret_doors": bool(getattr(self._render_cfg, "show_secret_doors", True)),
                "show_labels": bool(getattr(self._render_cfg, "show_labels", True)),
                "show_keys": bool(getattr(self._render_cfg, "show_keys", False)),
                "show_traps": bool(getattr(self._render_cfg, "show_traps", False)),
                "show_encounters": bool(getattr(self._render_cfg, "show_encounters", False)),
                "show_faction": bool(getattr(self._render_cfg, "show_faction", False)),
            },
            "preview": self._preview.export_window_state() if self._preview else (self._preview_state or {}),
        }
        return state

    def load_state(self, state: dict) -> None:
        state = state or {}
        for key, widget, cast in [
            ("w", self.w, int),
            ("h", self.h, int),
            ("seed", self.seed, int),
            ("max_rooms", self.max_rooms, int),
            ("room_attempts", self.room_attempts, int),
            ("min_room", self.min_room, int),
            ("max_room", self.max_room, int),
            ("corridor_width", self.corridor_width, int),
            ("danger", self.danger, int),
            ("cell_size", self.cell_size, int),
            ("secret_doors", self.secret_doors, int),
            ("secret_corridors", self.secret_corridors, int),
        ]:
            if key in state:
                try:
                    widget.setValue(cast(state[key]))
                except Exception:
                    pass

        for key, widget in [
            ("cave_mode", self.cave_mode),
        ]:
            if key in state:
                try:
                    widget.setChecked(bool(state[key]))
                except Exception:
                    pass

        for key, widget in [
            ("straightness", self.straightness),
            ("corridor_density", self.corridor_density),
            ("dead_end_prune", self.dead_end_prune),
        ]:
            if key in state:
                try:
                    widget.setValue(float(state[key]))
                except Exception:
                    pass

        # Render config toggles
        rc = state.get("render_cfg", {}) or {}
        self._render_cfg.cell_size = int(state.get("cell_size", self._render_cfg.cell_size))
        for k in rc:
            if hasattr(self._render_cfg, k):
                try:
                    setattr(self._render_cfg, k, bool(rc[k]))
                except Exception:
                    pass
        self.map_view.set_render_config(self._render_cfg)

        # Preview window persistence
        self._preview_state = state.get("preview", {}) or {}
