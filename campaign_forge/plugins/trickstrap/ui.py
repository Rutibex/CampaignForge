from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict, Optional, List
import random

# Qt import compatibility (PySide6 first, then PyQt5)
try:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
        QSpinBox, QSlider, QPlainTextEdit, QGroupBox, QFormLayout, QCheckBox,
        QMessageBox
    )
except Exception:  # pragma: no cover
    from PyQt5.QtCore import Qt
    from PyQt5.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
        QSpinBox, QSlider, QPlainTextEdit, QGroupBox, QFormLayout, QCheckBox,
        QMessageBox
    )

from .generator import INTENTS, generate_trap, TrapResult
from .exports import export_trap_markdown


class TricksAndTrapsWidget(QWidget):
    """
    Tricks & Traps Generator (OSR-first, 5e-compatible)
    - Ad-lib composition
    - Always produces tells + counterplay
    - Can export and send to scratchpad
    """

    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx
        self.plugin_id = "trickstrap"
        self.generate_count = 0
        self.last_trap: Optional[TrapResult] = None
        self.last_seed_used: int = 0

        self._build_ui()

    # -------------------------
    # UI
    # -------------------------

    def _build_ui(self):
        root = QVBoxLayout(self)

        header = QHBoxLayout()
        header.addWidget(QLabel("<b>Tricks & Traps (Ad-Lib Generator)</b>"))
        header.addStretch(1)
        self.btn_generate = QPushButton("Generate")
        self.btn_generate.clicked.connect(self.on_generate)
        header.addWidget(self.btn_generate)

        self.btn_to_scratch = QPushButton("Send to Scratchpad")
        self.btn_to_scratch.clicked.connect(self.on_send_to_scratchpad)
        header.addWidget(self.btn_to_scratch)

        self.btn_export = QPushButton("Export Markdown")
        self.btn_export.clicked.connect(self.on_export_md)
        header.addWidget(self.btn_export)

        root.addLayout(header)

        # Controls
        controls = QGroupBox("Tuning Knobs (OSR-first, 5e-based)")
        form = QFormLayout(controls)

        self.cmb_intent = QComboBox()
        self.cmb_intent.addItems(INTENTS)
        form.addRow("Trap Intent", self.cmb_intent)

        self.spin_tier = QSpinBox()
        self.spin_tier.setRange(1, 4)
        self.spin_tier.setValue(1)
        form.addRow("Tier (1–4)", self.spin_tier)

        self.spin_lethality = QSpinBox()
        self.spin_lethality.setRange(0, 4)
        self.spin_lethality.setValue(1)
        form.addRow("Lethality (0–4)", self.spin_lethality)

        self.spin_complexity = QSpinBox()
        self.spin_complexity.setRange(0, 4)
        self.spin_complexity.setValue(1)
        form.addRow("Complexity (0–4)", self.spin_complexity)

        self.sld_magic = QSlider(Qt.Horizontal)
        self.sld_magic.setRange(0, 100)
        self.sld_magic.setValue(50)
        form.addRow("Magic vs Mechanical", self.sld_magic)

        self.sld_weird = QSlider(Qt.Horizontal)
        self.sld_weird.setRange(0, 100)
        self.sld_weird.setValue(35)
        form.addRow("Weirdness", self.sld_weird)

        self.cmb_damage = QComboBox()
        self.cmb_damage.addItems(["Never", "Sometimes", "Often"])
        self.cmb_damage.setCurrentText("Sometimes")
        form.addRow("Include Damage", self.cmb_damage)

        self.cmb_reset = QComboBox()
        self.cmb_reset.addItems(["Any", "One-shot", "Manual", "Auto", "Persistent", "Degrades", "Improves"])
        form.addRow("Reset Bias", self.cmb_reset)

        self.chk_include_context_tags = QCheckBox("Add context tags (Dungeon/Room) from UI fields below")
        self.chk_include_context_tags.setChecked(True)
        form.addRow("", self.chk_include_context_tags)

        self.txt_context = QPlainTextEdit()
        self.txt_context.setPlaceholderText("Optional context tags, comma-separated. Example:\nDungeon:WakeWard, Room:9, Faction:Cult")
        self.txt_context.setFixedHeight(55)
        form.addRow("Context Tags", self.txt_context)

        root.addWidget(controls)

        # Output panes
        out_row = QHBoxLayout()

        self.view_trap = QPlainTextEdit()
        self.view_trap.setReadOnly(True)
        self.view_trap.setPlaceholderText("Generated trap output will appear here…")

        self.view_player = QPlainTextEdit()
        self.view_player.setReadOnly(True)
        self.view_player.setPlaceholderText("Player-facing tells / clues will appear here…")

        out_row.addWidget(self._wrap("GM Output (Full Markdown)", self.view_trap), 2)
        out_row.addWidget(self._wrap("Player-Facing Clues (Read Aloud-ish)", self.view_player), 1)

        root.addLayout(out_row)

        self._set_buttons_enabled(False)

    def _wrap(self, title: str, widget: QWidget) -> QGroupBox:
        box = QGroupBox(title)
        lay = QVBoxLayout(box)
        lay.addWidget(widget)
        return box

    def _set_buttons_enabled(self, has_trap: bool):
        self.btn_to_scratch.setEnabled(has_trap)
        self.btn_export.setEnabled(has_trap)

    # -------------------------
    # State persistence
    # -------------------------

    def serialize_state(self) -> Dict[str, Any]:
        return {
            "version": 1,
            "ui": {
                "intent": self.cmb_intent.currentText(),
                "tier": self.spin_tier.value(),
                "lethality": self.spin_lethality.value(),
                "complexity": self.spin_complexity.value(),
                "magic_vs_mech": self.sld_magic.value(),
                "weirdness": self.sld_weird.value(),
                "include_damage": self.cmb_damage.currentText(),
                "reset_bias": self.cmb_reset.currentText(),
                "context_tags": self.txt_context.toPlainText(),
                "include_context_tags": self.chk_include_context_tags.isChecked(),
            },
            "data": {
                "generate_count": self.generate_count,
                "last_seed_used": self.last_seed_used,
                "last_trap_md": self.view_trap.toPlainText(),
                "last_player_clues": self.view_player.toPlainText(),
            }
        }

    def load_state(self, state: Dict[str, Any]) -> None:
        if not state:
            return
        ui = state.get("ui", {})
        self.cmb_intent.setCurrentText(ui.get("intent", self.cmb_intent.currentText()))
        self.spin_tier.setValue(int(ui.get("tier", 1)))
        self.spin_lethality.setValue(int(ui.get("lethality", 1)))
        self.spin_complexity.setValue(int(ui.get("complexity", 1)))
        self.sld_magic.setValue(int(ui.get("magic_vs_mech", 50)))
        self.sld_weird.setValue(int(ui.get("weirdness", 35)))
        self.cmb_damage.setCurrentText(ui.get("include_damage", "Sometimes"))
        self.cmb_reset.setCurrentText(ui.get("reset_bias", "Any"))
        self.txt_context.setPlainText(ui.get("context_tags", ""))
        self.chk_include_context_tags.setChecked(bool(ui.get("include_context_tags", True)))

        data = state.get("data", {})
        self.generate_count = int(data.get("generate_count", 0))
        self.last_seed_used = int(data.get("last_seed_used", 0))
        self.view_trap.setPlainText(data.get("last_trap_md", ""))
        self.view_player.setPlainText(data.get("last_player_clues", ""))

        # We can't reliably reconstruct TrapResult without storing full fields,
        # but we can still re-enable actions if output exists.
        has = bool(self.view_trap.toPlainText().strip())
        self._set_buttons_enabled(has)

    # -------------------------
    # Actions
    # -------------------------

    def _derive_rng_and_seed(self) -> random.Random:
        # Preferred: ctx.derive_rng(master_seed, plugin_id, "generate", iteration)
        self.generate_count += 1
        iteration = self.generate_count

        if hasattr(self.ctx, "derive_rng"):
            try:
                rng = self.ctx.derive_rng(self.ctx.master_seed, self.plugin_id, "generate", iteration)
                # Try to surface a deterministic "seed used" if rng exposes it; else make one.
                self.last_seed_used = (self.ctx.master_seed * 1000003 + iteration * 9176) & 0x7fffffff
                return rng
            except Exception as e:
                self.ctx.log(f"[Tricks&Traps] derive_rng failed, falling back to random.Random. {e}")

        # fallback: deterministic-ish seed
        base = getattr(self.ctx, "master_seed", 1337)
        self.last_seed_used = (int(base) * 1000003 + iteration * 9176) & 0x7fffffff
        return random.Random(self.last_seed_used)

    def _parse_context_tags(self) -> List[str]:
        if not self.chk_include_context_tags.isChecked():
            return []
        raw = self.txt_context.toPlainText().strip()
        if not raw:
            return []
        parts = [p.strip() for p in raw.split(",")]
        parts = [p for p in parts if p]
        # Normalize to avoid spaces in tags
        clean = []
        for p in parts:
            clean.append(p.replace(" ", ""))
        return clean

    def on_generate(self):
        rng = self._derive_rng_and_seed()

        intent = self.cmb_intent.currentText()
        tier = self.spin_tier.value()
        lethality = self.spin_lethality.value()
        complexity = self.spin_complexity.value()
        magic_vs_mech = self.sld_magic.value()
        weirdness = self.sld_weird.value()
        include_damage = self.cmb_damage.currentText()
        reset_style = self.cmb_reset.currentText()

        context_tags = self._parse_context_tags()

        trap = generate_trap(
            rng,
            intent=intent,
            lethality=lethality,
            complexity=complexity,
            tier=tier,
            magic_vs_mech=magic_vs_mech,
            weirdness=weirdness,
            reset_style=reset_style,
            include_damage=include_damage,
            context_tags=context_tags,
            seed_used=self.last_seed_used,
        )
        self.last_trap = trap

        md = trap.to_markdown()
        self.view_trap.setPlainText(md)

        # Player-facing clues pane: just the tells, plus a short read-aloud line
        player_lines = []
        player_lines.append(f"{trap.title} — what you notice:")
        player_lines.append("")
        for t in trap.tells:
            player_lines.append(f"- {t}")
        player_lines.append("")
        player_lines.append("(If the group slows down and investigates, give more detail or let them discover the trigger.)")
        self.view_player.setPlainText("\n".join(player_lines))

        self._set_buttons_enabled(True)
        self.ctx.log(f"[Tricks&Traps] Generated: {trap.title} (Seed {trap.seed_used})")

    def on_send_to_scratchpad(self):
        if not self.last_trap:
            return
        try:
            self.ctx.scratchpad_add(
                text=self.last_trap.to_markdown(),
                tags=self.last_trap.tags
            )
            self.ctx.log(f"[Tricks&Traps] Sent to scratchpad: {self.last_trap.title}")
        except Exception as e:
            self.ctx.log(f"[Tricks&Traps] Failed to send to scratchpad: {e}")
            QMessageBox.warning(self, "Tricks & Traps", f"Failed to send to scratchpad:\n{e}")

    def on_export_md(self):
        if not self.last_trap:
            return
        try:
            path = export_trap_markdown(self.ctx, self.last_trap)
            self.ctx.log(f"[Tricks&Traps] Exported Markdown: {path}")
        except Exception as e:
            self.ctx.log(f"[Tricks&Traps] Export failed: {e}")
            QMessageBox.warning(self, "Tricks & Traps", f"Export failed:\n{e}")
