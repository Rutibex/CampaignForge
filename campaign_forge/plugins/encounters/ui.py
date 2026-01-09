from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QAction
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QTextEdit, QLineEdit, QComboBox,
    QSpinBox, QCheckBox, QGroupBox, QTabWidget, QMessageBox, QSlider
)

from .generator import EncounterInputs, generate_encounter
from .exports import export_session_pack


class EncounterGeneratorWidget(QWidget):
    PLUGIN_ID = "encounters"

    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx
        self._tables_dir = Path(__file__).parent / "tables"

        self._iteration = 0
        self._last_result = None  # EncounterResult

        self._build_ui()

    # ---------------- UI ----------------

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        # Controls group
        controls = QGroupBox("Encounter Inputs")
        root.addWidget(controls)
        g = QGridLayout(controls)
        g.setHorizontalSpacing(10)
        g.setVerticalSpacing(8)

        row = 0

        # Party context
        g.addWidget(QLabel("Party Level"), row, 0)
        self.party_level = QSpinBox()
        self.party_level.setRange(1, 20)
        self.party_level.setValue(3)
        g.addWidget(self.party_level, row, 1)

        g.addWidget(QLabel("Party Size"), row, 2)
        self.party_size = QSpinBox()
        self.party_size.setRange(1, 10)
        self.party_size.setValue(4)
        g.addWidget(self.party_size, row, 3)
        row += 1

        g.addWidget(QLabel("Party Condition"), row, 0)
        self.party_condition = QComboBox()
        self.party_condition.addItems(["Fresh", "Wounded", "Exhausted", "Desperate"])
        g.addWidget(self.party_condition, row, 1)

        g.addWidget(QLabel("Difficulty Intent"), row, 2)
        self.difficulty = QComboBox()
        self.difficulty.addItems(["Easy", "Medium", "Hard", "Deadly"])
        self.difficulty.setCurrentText("Medium")
        g.addWidget(self.difficulty, row, 3)
        row += 1

        # World context
        g.addWidget(QLabel("Biome"), row, 0)
        self.biome = QComboBox()
        self.biome.addItems(["Dungeon", "Forest", "Swamp", "Desert", "Urban", "Cavern"])
        g.addWidget(self.biome, row, 1)

        g.addWidget(QLabel("Dungeon Tag"), row, 2)
        self.dungeon_tag = QLineEdit()
        self.dungeon_tag.setPlaceholderText("e.g., Wake Ward, Abandoned Temple")
        g.addWidget(self.dungeon_tag, row, 3)
        row += 1

        g.addWidget(QLabel("Faction (name)"), row, 0)
        self.faction_name = QLineEdit()
        self.faction_name.setPlaceholderText("e.g., Ashen Veil, City Watch")
        g.addWidget(self.faction_name, row, 1)

        g.addWidget(QLabel("Faction Profile"), row, 2)
        self.faction_profile = QComboBox()
        self.faction_profile.addItems(["Auto", "Bandits / Raiders", "Cult Cell", "Militia / Watch", "Undead Presence", "Territorial Monsters"])
        g.addWidget(self.faction_profile, row, 3)
        row += 1

        # Intent
        g.addWidget(QLabel("Encounter Type"), row, 0)
        self.encounter_type = QComboBox()
        self.encounter_type.addItems([
            "Auto",
            "Patrol / Sweep",
            "Ambush",
            "Guard Post / Checkpoint",
            "Ritual / Operation",
            "Scavengers / Looters",
            "Hazard + Creatures",
            "Social / Negotiation Under Threat",
            "Chase / Pursuit",
        ])
        g.addWidget(self.encounter_type, row, 1)

        g.addWidget(QLabel("Narrative Role"), row, 2)
        self.narrative_role = QComboBox()
        self.narrative_role.addItems(["Neutral", "Foreshadowing", "Attrition", "Climax", "Complication"])
        g.addWidget(self.narrative_role, row, 3)
        row += 1

        g.addWidget(QLabel("Lethality"), row, 0)
        self.lethality = QSlider(Qt.Horizontal)
        self.lethality.setRange(0, 100)
        self.lethality.setValue(50)
        g.addWidget(self.lethality, row, 1)

        self.lethality_label = QLabel("50")
        self.lethality.valueChanged.connect(lambda v: self.lethality_label.setText(str(v)))
        g.addWidget(self.lethality_label, row, 2)

        self.allow_social = QCheckBox("Allow social outcomes")
        self.allow_social.setChecked(True)
        g.addWidget(self.allow_social, row, 3)
        row += 1

        self.allow_hazard = QCheckBox("Allow hazard complications")
        self.allow_hazard.setChecked(True)
        g.addWidget(self.allow_hazard, row, 0, 1, 2)

        self.chain_mode = QCheckBox("Generate follow-up chain")
        self.chain_mode.setChecked(False)
        g.addWidget(self.chain_mode, row, 2)
        self.chain_steps = QSpinBox()
        self.chain_steps.setRange(2, 3)
        self.chain_steps.setValue(2)
        self.chain_steps.setEnabled(False)
        self.chain_mode.toggled.connect(self.chain_steps.setEnabled)
        g.addWidget(self.chain_steps, row, 3)

        # Seed lock
        self.lock_seed = QCheckBox("Lock seed")
        g.addWidget(self.lock_seed, row, 2)
        self.seed = QSpinBox()
        self.seed.setRange(0, 2_000_000_000)
        self.seed.setValue(0)
        self.seed.setEnabled(False)
        self.lock_seed.toggled.connect(self.seed.setEnabled)
        g.addWidget(self.seed, row, 3)
        row += 1

        # Notes
        g.addWidget(QLabel("GM Intent / Notes"), row, 0)
        self.notes = QLineEdit()
        self.notes.setPlaceholderText("Optional: what do you want this scene to do?")
        g.addWidget(self.notes, row, 1, 1, 3)
        row += 1

        # Buttons row
        btn_row = QHBoxLayout()
        self.generate_btn = QPushButton("Generate Encounter")
        self.copy_btn = QPushButton("Copy Markdown")
        self.copy_btn.setEnabled(False)
        self.scratch_btn = QPushButton("Send to Scratchpad")
        self.scratch_btn.setEnabled(False)
        self.export_btn = QPushButton("Export Session Pack")
        self.export_btn.setEnabled(False)

        btn_row.addWidget(self.generate_btn)
        btn_row.addWidget(self.copy_btn)
        btn_row.addWidget(self.scratch_btn)
        btn_row.addWidget(self.export_btn)

        root.addLayout(btn_row)

        # Output tabs
        self.tabs = QTabWidget()
        root.addWidget(self.tabs, 1)

        self.out_md = QTextEdit()
        self.out_md.setReadOnly(True)
        self.out_md.setFont(QFont("Consolas", 10))
        self.tabs.addTab(self.out_md, "Encounter (Markdown)")

        self.out_json = QTextEdit()
        self.out_json.setReadOnly(True)
        self.out_json.setFont(QFont("Consolas", 10))
        self.tabs.addTab(self.out_json, "Data (JSON)")

        # Wire up actions
        self.generate_btn.clicked.connect(self._on_generate)
        self.copy_btn.clicked.connect(self._on_copy)
        self.scratch_btn.clicked.connect(self._on_send_scratchpad)
        self.export_btn.clicked.connect(self._on_export)

    # ---------------- State ----------------

    def serialize_state(self) -> dict:
        return {
            "version": 1,
            "ui": {
                "party_level": self.party_level.value(),
                "party_size": self.party_size.value(),
                "party_condition": self.party_condition.currentText(),
                "biome": self.biome.currentText(),
                "dungeon_tag": self.dungeon_tag.text(),
                "faction_name": self.faction_name.text(),
                "faction_profile": self.faction_profile.currentText(),
                "encounter_type": self.encounter_type.currentText(),
                "difficulty": self.difficulty.currentText(),
                "narrative_role": self.narrative_role.currentText(),
                "lethality": self.lethality.value(),
                "allow_social": self.allow_social.isChecked(),
                "allow_hazard": self.allow_hazard.isChecked(),
                "chain_mode": self.chain_mode.isChecked(),
                "chain_steps": self.chain_steps.value(),
                "lock_seed": self.lock_seed.isChecked(),
                "seed": self.seed.value(),
                "notes": self.notes.text(),
            },
            "data": {
                "iteration": int(self._iteration),
                "last_markdown": self.out_md.toPlainText(),
                "last_json": self.out_json.toPlainText(),
                "last_seed": int(getattr(self._last_result, "seed_used", 0) or 0) if self._last_result else 0,
                "last_title": str(getattr(self._last_result, "title", "")) if self._last_result else "",
            }
        }

    def load_state(self, state: dict) -> None:
        if not state:
            return
        ver = int(state.get("version", 1))
        if ver != 1:
            self.ctx.log(f"[encounters] Unknown state version: {ver}")
            return

        ui = state.get("ui", {}) or {}
        self.party_level.setValue(int(ui.get("party_level", 3)))
        self.party_size.setValue(int(ui.get("party_size", 4)))
        self.party_condition.setCurrentText(str(ui.get("party_condition", "Fresh")))
        self.biome.setCurrentText(str(ui.get("biome", "Dungeon")))
        self.dungeon_tag.setText(str(ui.get("dungeon_tag", "")))
        self.faction_name.setText(str(ui.get("faction_name", "")))
        self.faction_profile.setCurrentText(str(ui.get("faction_profile", "Auto")))
        self.encounter_type.setCurrentText(str(ui.get("encounter_type", "Auto")))
        self.difficulty.setCurrentText(str(ui.get("difficulty", "Medium")))
        self.narrative_role.setCurrentText(str(ui.get("narrative_role", "Neutral")))
        self.lethality.setValue(int(ui.get("lethality", 50)))
        self.allow_social.setChecked(bool(ui.get("allow_social", True)))
        self.allow_hazard.setChecked(bool(ui.get("allow_hazard", True)))
        self.chain_mode.setChecked(bool(ui.get("chain_mode", False)))
        self.chain_steps.setValue(int(ui.get("chain_steps", 2)))
        self.lock_seed.setChecked(bool(ui.get("lock_seed", False)))
        self.seed.setValue(int(ui.get("seed", 0)))
        self.notes.setText(str(ui.get("notes", "")))

        data = state.get("data", {}) or {}
        self._iteration = int(data.get("iteration", 0))
        last_md = str(data.get("last_markdown", ""))
        last_js = str(data.get("last_json", ""))
        if last_md.strip():
            self.out_md.setPlainText(last_md)
            self.out_json.setPlainText(last_js)
            self.copy_btn.setEnabled(True)
            self.scratch_btn.setEnabled(True)
            self.export_btn.setEnabled(True)

    # ---------------- Internals ----------------

    def _inputs(self) -> EncounterInputs:
        # Map display strings to ids used in tables
        faction_profile_map = {
            "Auto": "Auto",
            "Bandits / Raiders": "bandits",
            "Cult Cell": "cult",
            "Militia / Watch": "militia",
            "Undead Presence": "undead",
            "Territorial Monsters": "monsters",
        }
        encounter_type_map = {
            "Auto": "Auto",
            "Patrol / Sweep": "patrol",
            "Ambush": "ambush",
            "Guard Post / Checkpoint": "guardpost",
            "Ritual / Operation": "ritual",
            "Scavengers / Looters": "scavengers",
            "Hazard + Creatures": "hazard",
            "Social / Negotiation Under Threat": "social",
            "Chase / Pursuit": "chase",
        }

        return EncounterInputs(
            party_level=int(self.party_level.value()),
            party_size=int(self.party_size.value()),
            party_condition=str(self.party_condition.currentText()),
            biome=str(self.biome.currentText()),
            dungeon_tag=str(self.dungeon_tag.text()),
            faction=str(self.faction_name.text()),
            faction_profile=str(faction_profile_map.get(self.faction_profile.currentText(), "Auto")),
            encounter_type=str(encounter_type_map.get(self.encounter_type.currentText(), "Auto")),
            difficulty=str(self.difficulty.currentText()),
            narrative_role=str(self.narrative_role.currentText()),
            lethality=int(self.lethality.value()),
            allow_social=bool(self.allow_social.isChecked()),
            allow_hazard=bool(self.allow_hazard.isChecked()),
            chain_mode=bool(self.chain_mode.isChecked()),
            chain_steps=int(self.chain_steps.value()),
            lock_seed=bool(self.lock_seed.isChecked()),
            seed=int(self.seed.value()),
            notes=str(self.notes.text()),
        )

    def _on_generate(self):
        try:
            inp = self._inputs()
            self._iteration += 1
            res = generate_encounter(self.ctx, self._tables_dir, inp, iteration=self._iteration)
            self._last_result = res

            self.out_md.setPlainText(res.markdown)
            import json
            self.out_json.setPlainText(json.dumps(asdict(res), indent=2))

            self.copy_btn.setEnabled(True)
            self.scratch_btn.setEnabled(True)
            self.export_btn.setEnabled(True)

            self.ctx.log(f"[encounters] Generated: {res.title} (seed {res.seed_used})")
        except Exception as e:
            self.ctx.log(f"[encounters] Generation failed: {e}")
            QMessageBox.critical(self, "Encounter Generator Error", f"Generation failed:\n\n{e}")

    def _on_copy(self):
        text = self.out_md.toPlainText().strip()
        if not text:
            return
        try:
            from PySide6.QtWidgets import QApplication
            QApplication.clipboard().setText(text)
            self.ctx.log("[encounters] Copied markdown to clipboard.")
        except Exception as e:
            self.ctx.log(f"[encounters] Clipboard copy failed: {e}")

    def _on_send_scratchpad(self):
        if not getattr(self.ctx, "scratchpad_add", None):
            QMessageBox.warning(self, "Scratchpad unavailable", "Scratchpad service is not available.")
            return
        if not self._last_result:
            return
        try:
            self.ctx.scratchpad_add(self._last_result.markdown, tags=self._last_result.tags)
            self.ctx.log(f"[encounters] Sent to scratchpad: {self._last_result.title}")
        except Exception as e:
            self.ctx.log(f"[encounters] Failed to send to scratchpad: {e}")

    def _on_export(self):
        if not self._last_result:
            return
        try:
            slug = (self._last_result.title or "encounter").strip()
            pack_dir = export_session_pack(self.ctx, self._last_result, slug=slug)
            self.ctx.log(f"[encounters] Exported session pack: {pack_dir}")
            QMessageBox.information(self, "Export complete", f"Exported to:\n{pack_dir}")
        except Exception as e:
            self.ctx.log(f"[encounters] Export failed: {e}")
            QMessageBox.critical(self, "Export failed", f"Export failed:\n\n{e}")
