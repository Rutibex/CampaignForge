from __future__ import annotations

import random
from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QPushButton,
    QTextEdit, QComboBox, QCheckBox, QSpinBox, QFormLayout
)

from campaign_forge.plugins.hexmap.generator import BUILTIN_THEMES
from campaign_forge.plugins.dungeonmap.generator import DungeonGenConfig

from .generator import generate_location_stack, LocationStack, stack_to_markdown
from .exports import export_session_pack

# Name styles supported by the built-in names plugin
NAME_STYLES = ["Fantasy", "Elven", "Dwarven", "Guttural"]


class LocationStackWidget(QWidget):
    PLUGIN_ID = "location_stack"

    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx
        self._stack: Optional[LocationStack] = None
        self._generate_count = 0
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)

        controls = QGroupBox("Location Stack Generator (Region → Site → Sub-site → Room)")
        form = QFormLayout()
        controls.setLayout(form)

        self.theme = QComboBox()
        for k in sorted(BUILTIN_THEMES.keys()):
            self.theme.addItem(k)
        self.theme.setCurrentText("OSR" if "OSR" in BUILTIN_THEMES else self.theme.itemText(0))
        form.addRow("Region theme:", self.theme)

        self.name_style = QComboBox()
        for s in NAME_STYLES:
            self.name_style.addItem(s)
        self.name_style.setCurrentText("Fantasy")
        form.addRow("Name style:", self.name_style)

        row_attach = QHBoxLayout()
        self.attach_dungeon = QCheckBox("Attach dungeon"); self.attach_dungeon.setChecked(True)
        self.attach_faction = QCheckBox("Attach faction"); self.attach_faction.setChecked(True)
        self.attach_rumors = QCheckBox("Attach rumors"); self.attach_rumors.setChecked(True)
        row_attach.addWidget(self.attach_dungeon)
        row_attach.addWidget(self.attach_faction)
        row_attach.addWidget(self.attach_rumors)
        row_attach.addStretch(1)
        form.addRow("Attachments:", row_attach)

        self.rumor_count = QSpinBox()
        self.rumor_count.setRange(1, 12)
        self.rumor_count.setValue(6)
        form.addRow("Rumor count:", self.rumor_count)

        dungeon_box = QGroupBox("Dungeon knobs (donjon-ish)")
        dform = QFormLayout()
        dungeon_box.setLayout(dform)

        self.max_rooms = QSpinBox(); self.max_rooms.setRange(4, 60); self.max_rooms.setValue(18)
        self.corridor_density = QSpinBox(); self.corridor_density.setRange(0, 100); self.corridor_density.setValue(35)
        self.dead_end_prune = QSpinBox(); self.dead_end_prune.setRange(0, 100); self.dead_end_prune.setValue(25)
        self.cave_mode = QCheckBox("Cave mode"); self.cave_mode.setChecked(False)
        self.secret_doors = QSpinBox(); self.secret_doors.setRange(0, 12); self.secret_doors.setValue(2)
        self.secret_corridors = QSpinBox(); self.secret_corridors.setRange(0, 12); self.secret_corridors.setValue(1)

        dform.addRow("Max rooms:", self.max_rooms)
        dform.addRow("Corridor density (%):", self.corridor_density)
        dform.addRow("Dead-end prune (%):", self.dead_end_prune)
        dform.addRow("", self.cave_mode)
        dform.addRow("Secret doors:", self.secret_doors)
        dform.addRow("Secret corridors:", self.secret_corridors)

        root.addWidget(controls)
        root.addWidget(dungeon_box)

        btns = QHBoxLayout()
        self.generate_btn = QPushButton("Generate Location Stack")
        self.send_btn = QPushButton("Send to Scratchpad")
        self.export_btn = QPushButton("Export Session Pack")
        self.send_btn.setEnabled(False)
        self.export_btn.setEnabled(False)
        btns.addWidget(self.generate_btn)
        btns.addWidget(self.send_btn)
        btns.addWidget(self.export_btn)
        btns.addStretch(1)

        self.split_scratchpad = QCheckBox("Split scratchpad entries by layer")
        self.split_scratchpad.setChecked(True)
        btns.addWidget(self.split_scratchpad)

        root.addLayout(btns)

        self.out = QTextEdit()
        self.out.setReadOnly(True)
        self.out.setPlaceholderText("Generate a stack to see results here…")
        root.addWidget(self.out, 1)

        self.generate_btn.clicked.connect(self.on_generate)
        self.send_btn.clicked.connect(self.on_send_to_scratchpad)
        self.export_btn.clicked.connect(self.on_export)

        self.attach_dungeon.toggled.connect(self._update_dungeon_knobs)
        self._update_dungeon_knobs()

    def _update_dungeon_knobs(self) -> None:
        enabled = self.attach_dungeon.isChecked()
        for w in [self.max_rooms, self.corridor_density, self.dead_end_prune, self.cave_mode, self.secret_doors, self.secret_corridors]:
            w.setEnabled(enabled)

    def _make_dungeon_cfg(self) -> DungeonGenConfig:
        cfg = DungeonGenConfig()
        cfg.max_rooms = int(self.max_rooms.value())
        cfg.corridor_density = float(self.corridor_density.value()) / 100.0
        cfg.dead_end_prune = float(self.dead_end_prune.value()) / 100.0
        cfg.cave_mode = bool(self.cave_mode.isChecked())
        cfg.secret_doors = int(self.secret_doors.value())
        cfg.secret_corridors = int(self.secret_corridors.value())
        return cfg

    def on_generate(self) -> None:
        self._generate_count += 1
        seed = self.ctx.derive_seed(self.PLUGIN_ID, "generate", self._generate_count)
        rng = random.Random(seed)
        try:
            rng._seed = seed  # type: ignore[attr-defined]
        except Exception:
            pass

        stack = generate_location_stack(
            rng,
            theme=self.theme.currentText().strip() or "OSR",
            name_style=self.name_style.currentText().strip() or "Fantasy",
            attach_dungeon=self.attach_dungeon.isChecked(),
            dungeon_cfg=self._make_dungeon_cfg(),
            attach_faction=self.attach_faction.isChecked(),
            attach_rumors=self.attach_rumors.isChecked(),
            rumor_count=int(self.rumor_count.value()),
        )
        stack.seed = seed  # type: ignore[misc]
        self._stack = stack

        self.out.setPlainText(stack_to_markdown(stack))
        self.send_btn.setEnabled(True)
        self.export_btn.setEnabled(True)
        self.ctx.log(f"[LocationStack] Generated stack (seed={seed}).")

    def _send_entry(self, title: str, text: str, tags: list[str]) -> None:
        payload = f"## {title}\n\n{text}".strip() + "\n"
        self.ctx.scratchpad_add(payload, tags=tags)

    def on_send_to_scratchpad(self) -> None:
        if not self._stack:
            return
        stack = self._stack

        if not self.split_scratchpad.isChecked():
            self.ctx.scratchpad_add(stack_to_markdown(stack), tags=["LocationStack"] + stack.site.tags)
            self.ctx.log("[LocationStack] Sent single entry to scratchpad.")
            return

        self._send_entry(
            "Region",
            f"**{stack.region.name}** — Theme **{stack.region.theme}**, terrain **{stack.region.terrain}**.\n\n"
            f"Encounters: " + ", ".join(stack.region.content.get("encounters", [])) + "\n\n"
            f"Hazards: " + ", ".join(stack.region.content.get("hazards", [])) + "\n\n"
            f"Resources: " + ", ".join(stack.region.content.get("resources", [])),
            tags=stack.region.tags,
        )

        self._send_entry(
            "Site",
            f"**{stack.site.name}** ({stack.site.site_type}) — POI vibe: **{stack.site.poi}**.\n\n"
            + "\n".join(f"- {n}" for n in stack.site.notes),
            tags=stack.site.tags,
        )

        if stack.faction:
            self._send_entry(
                "Faction",
                f"**{stack.faction.name}** ({stack.faction.faction_type})\n\n"
                + "**Methods:**\n" + "\n".join(f"- {m}" for m in stack.faction.methods)
                + "\n\n**Hooks:**\n" + "\n".join(f"- {h}" for h in stack.faction.hooks),
                tags=stack.faction.tags,
            )

        if stack.rumors:
            self._send_entry(
                "Rumors",
                "\n".join(f"{i+1}. {r}" for i, r in enumerate(stack.rumors.rumors)),
                tags=stack.rumors.tags,
            )

        if stack.subsite.dungeon:
            from campaign_forge.plugins.dungeonmap.generator import dungeon_contents_text
            self._send_entry(
                "Sub-site",
                f"**{stack.subsite.name}** ({stack.subsite.subsite_type})\n\n"
                f"*Dungeon seed:* **{stack.subsite.dungeon_seed}**\n\n"
                "### Room Key & Contents\n\n"
                + dungeon_contents_text(stack.subsite.dungeon),
                tags=stack.subsite.tags,
            )
        else:
            self._send_entry(
                "Sub-site",
                f"**{stack.subsite.name}** ({stack.subsite.subsite_type})\n\n_No dungeon attached._",
                tags=stack.subsite.tags,
            )

        self.ctx.log("[LocationStack] Sent layered entries to scratchpad.")

    def on_export(self) -> None:
        if not self._stack:
            return
        written = export_session_pack(self.ctx, self._stack, title="location_stack")
        pack_dir = next(iter(written.values())).parent if written else (self.ctx.project_dir / "exports")
        self.ctx.log(f"[LocationStack] Exported session pack: {pack_dir}")

    def serialize_state(self) -> dict:
        return {
            "version": 1,
            "generate_count": int(self._generate_count),
            "theme": self.theme.currentText(),
            "name_style": self.name_style.currentText(),
            "attach_dungeon": bool(self.attach_dungeon.isChecked()),
            "attach_faction": bool(self.attach_faction.isChecked()),
            "attach_rumors": bool(self.attach_rumors.isChecked()),
            "rumor_count": int(self.rumor_count.value()),
            "dungeon": {
                "max_rooms": int(self.max_rooms.value()),
                "corridor_density": int(self.corridor_density.value()),
                "dead_end_prune": int(self.dead_end_prune.value()),
                "cave_mode": bool(self.cave_mode.isChecked()),
                "secret_doors": int(self.secret_doors.value()),
                "secret_corridors": int(self.secret_corridors.value()),
            },
            "split_scratchpad": bool(self.split_scratchpad.isChecked()),
        }

    def load_state(self, state: dict) -> None:
        state = state or {}
        try: self._generate_count = int(state.get("generate_count", 0))
        except Exception: self._generate_count = 0

        t = str(state.get("theme", self.theme.currentText()))
        i = self.theme.findText(t)
        if i >= 0: self.theme.setCurrentIndex(i)

        ns = str(state.get("name_style", self.name_style.currentText()))
        i = self.name_style.findText(ns)
        if i >= 0: self.name_style.setCurrentIndex(i)

        self.attach_dungeon.setChecked(bool(state.get("attach_dungeon", True)))
        self.attach_faction.setChecked(bool(state.get("attach_faction", True)))
        self.attach_rumors.setChecked(bool(state.get("attach_rumors", True)))

        try: self.rumor_count.setValue(int(state.get("rumor_count", self.rumor_count.value())))
        except Exception: pass

        d = state.get("dungeon", {}) or {}
        for key, widget in [
            ("max_rooms", self.max_rooms),
            ("corridor_density", self.corridor_density),
            ("dead_end_prune", self.dead_end_prune),
            ("secret_doors", self.secret_doors),
            ("secret_corridors", self.secret_corridors),
        ]:
            try:
                widget.setValue(int(d.get(key, widget.value())))
            except Exception:
                pass
        try: self.cave_mode.setChecked(bool(d.get("cave_mode", self.cave_mode.isChecked())))
        except Exception: pass

        self.split_scratchpad.setChecked(bool(state.get("split_scratchpad", True)))
        self._update_dungeon_knobs()
