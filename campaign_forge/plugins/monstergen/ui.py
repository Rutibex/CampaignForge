# campaign_forge/plugins/monstergen/ui.py

from __future__ import annotations

from typing import Optional, Dict, Any

# ---- Qt binding compatibility layer (PySide6 preferred) ----
try:
    from PySide6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
        QLineEdit, QTextEdit, QGroupBox, QFormLayout, QCheckBox, QSpinBox
    )
    from PySide6.QtCore import Qt
except ModuleNotFoundError:
    # Fallback if the host app uses PyQt5
    from PyQt5.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
        QLineEdit, QTextEdit, QGroupBox, QFormLayout, QCheckBox, QSpinBox
    )
    from PyQt5.QtCore import Qt

from .tables import CREATURE_TYPES, SIZES, ALIGNMENTS, ROLES
from .generator import generate_monster, monster_to_markdown, parse_cr_label, cr_label
from .exports import export_monster_session_pack


CR_CHOICES = ["0", "1/8", "1/4", "1/2"] + [str(i) for i in range(1, 31)]


class MonsterGenWidget(QWidget):
    """
    Campaign Forge Monster Generator (5e statblock compatible)

    Expected context methods used:
      - ctx.log(str)
      - ctx.master_seed (or ctx.project settings)
      - ctx.derive_rng(master_seed, plugin_id, action, iteration) -> random.Random-like
      - ctx.scratchpad_add(text, tags=[...])
      - ctx.export_manager.create_session_pack(...)
    """

    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx
        self.plugin_id = "monstergen"

        self._generate_count = 0
        self._last_seed_used: Optional[int] = None
        self._last_monster_md: str = ""
        self._last_monster_name: str = ""
        self._build_ui()

    # ---------------- UI ----------------

    def _build_ui(self):
        root = QVBoxLayout(self)

        title = QLabel("Monster Generator (5e)")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        root.addWidget(title)

        # Controls group
        gb = QGroupBox("Generator Controls")
        form = QFormLayout(gb)

        self.cr_combo = QComboBox()
        self.cr_combo.addItems(CR_CHOICES)
        self.cr_combo.setCurrentText("3")

        self.role_combo = QComboBox()
        self.role_combo.addItems(ROLES)
        self.role_combo.setCurrentText("Brute")

        self.type_combo = QComboBox()
        self.type_combo.addItems(CREATURE_TYPES)
        self.type_combo.setCurrentText("Undead")

        self.size_combo = QComboBox()
        self.size_combo.addItems(SIZES)
        self.size_combo.setCurrentText("Medium")

        self.alignment_combo = QComboBox()
        self.alignment_combo.addItems(ALIGNMENTS)
        self.alignment_combo.setCurrentText("unaligned")

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Optional: leave blank for generated name")

        self.strict_math_chk = QCheckBox("Show CR audit (recommended)")
        self.strict_math_chk.setChecked(True)

        self.tags_edit = QLineEdit()
        self.tags_edit.setPlaceholderText("Extra tags (comma-separated), e.g. Swamp, Cult, Session-12")

        self.iter_spin = QSpinBox()
        self.iter_spin.setRange(0, 999999)
        self.iter_spin.setValue(0)
        self.iter_spin.setToolTip("Added to the internal generate counter to derive deterministic RNG.")

        form.addRow("Target CR", self.cr_combo)
        form.addRow("Role", self.role_combo)
        form.addRow("Creature Type", self.type_combo)
        form.addRow("Size", self.size_combo)
        form.addRow("Alignment", self.alignment_combo)
        form.addRow("Name (optional)", self.name_edit)
        form.addRow("Iteration Offset", self.iter_spin)
        form.addRow("", self.strict_math_chk)
        form.addRow("Extra Tags", self.tags_edit)

        root.addWidget(gb)

        # Buttons
        btn_row = QHBoxLayout()
        self.btn_generate = QPushButton("Generate")
        self.btn_reskin = QPushButton("Reskin Name Only")
        self.btn_scratchpad = QPushButton("Send to Scratchpad")
        self.btn_export = QPushButton("Export Session Pack")
        btn_row.addWidget(self.btn_generate)
        btn_row.addWidget(self.btn_reskin)
        btn_row.addWidget(self.btn_scratchpad)
        btn_row.addWidget(self.btn_export)
        root.addLayout(btn_row)

        # Output
        self.out = QTextEdit()
        self.out.setReadOnly(True)
        self.out.setPlaceholderText("Generated monster stat block will appear here.")
        root.addWidget(self.out, stretch=1)

        # Wire events
        self.btn_generate.clicked.connect(self.on_generate)
        self.btn_reskin.clicked.connect(self.on_reskin)
        self.btn_scratchpad.clicked.connect(self.on_send_scratchpad)
        self.btn_export.clicked.connect(self.on_export)

    # ---------------- Persistence ----------------

    def serialize_state(self) -> Dict[str, Any]:
        return {
            "version": 1,
            "ui": {
                "cr": self.cr_combo.currentText(),
                "role": self.role_combo.currentText(),
                "type": self.type_combo.currentText(),
                "size": self.size_combo.currentText(),
                "alignment": self.alignment_combo.currentText(),
                "name": self.name_edit.text(),
                "show_audit": self.strict_math_chk.isChecked(),
                "extra_tags": self.tags_edit.text(),
                "iter_offset": self.iter_spin.value(),
            },
            "data": {
                "generate_count": self._generate_count,
                "last_seed_used": self._last_seed_used,
                "last_monster_name": self._last_monster_name,
                "last_monster_md": self._last_monster_md,
            },
        }

    def load_state(self, state: Dict[str, Any]) -> None:
        if not state:
            return
        ver = state.get("version", 1)
        if ver != 1:
            self.ctx.log(f"[MonsterGen] Unknown state version {ver}; ignoring.")
            return

        ui = state.get("ui", {})
        self.cr_combo.setCurrentText(ui.get("cr", "3"))
        self.role_combo.setCurrentText(ui.get("role", "Brute"))
        self.type_combo.setCurrentText(ui.get("type", "Undead"))
        self.size_combo.setCurrentText(ui.get("size", "Medium"))
        self.alignment_combo.setCurrentText(ui.get("alignment", "unaligned"))
        self.name_edit.setText(ui.get("name", ""))
        self.strict_math_chk.setChecked(bool(ui.get("show_audit", True)))
        self.tags_edit.setText(ui.get("extra_tags", ""))
        self.iter_spin.setValue(int(ui.get("iter_offset", 0)))

        data = state.get("data", {})
        self._generate_count = int(data.get("generate_count", 0))
        self._last_seed_used = data.get("last_seed_used", None)
        self._last_monster_name = data.get("last_monster_name", "")
        self._last_monster_md = data.get("last_monster_md", "")

        if self._last_monster_md:
            self.out.setPlainText(self._apply_audit_visibility(self._last_monster_md))

    # ---------------- Actions ----------------

    def _derive_rng(self):
        try:
            master = self.ctx.master_seed
        except Exception:
            master = 1337  # fallback

        iteration = self._generate_count + int(self.iter_spin.value())
        rng = self.ctx.derive_rng(master, self.plugin_id, "generate", iteration)
        return rng, iteration

    def _apply_audit_visibility(self, md: str) -> str:
        if self.strict_math_chk.isChecked():
            return md
        marker = "\n---\n### CR Audit (Generator)\n"
        idx = md.find(marker)
        if idx >= 0:
            return md[:idx].rstrip() + "\n"
        return md

    def on_generate(self):
        try:
            target_cr = parse_cr_label(self.cr_combo.currentText())
            role = self.role_combo.currentText()
            ctype = self.type_combo.currentText()
            size = self.size_combo.currentText()
            align = self.alignment_combo.currentText()
            name = self.name_edit.text().strip() or None

            rng, iteration = self._derive_rng()
            mon = generate_monster(
                rng=rng,
                target_cr=target_cr,
                role=role,
                creature_type=ctype,
                size=size,
                alignment=align,
                name=name,
            )

            md = monster_to_markdown(mon)
            md = self._apply_audit_visibility(md)

            self._generate_count += 1
            self._last_seed_used = iteration
            self._last_monster_name = mon.name
            self._last_monster_md = md

            self.out.setPlainText(md)
            self.ctx.log(f"[MonsterGen] Generated {mon.name} (Target CR {cr_label(target_cr)} → Final CR {mon.cr}). Seed iteration={iteration}")
        except Exception as e:
            self.ctx.log(f"[MonsterGen] ERROR generating monster: {e}")

    def on_reskin(self):
        try:
            if not self._last_monster_md:
                self.ctx.log("[MonsterGen] Nothing to reskin yet — generate first.")
                return

            target_cr = parse_cr_label(self.cr_combo.currentText())
            role = self.role_combo.currentText()
            ctype = self.type_combo.currentText()
            size = self.size_combo.currentText()
            align = self.alignment_combo.currentText()

            rng, _iteration = self._derive_rng()
            mon = generate_monster(
                rng=rng,
                target_cr=target_cr,
                role=role,
                creature_type=ctype,
                size=size,
                alignment=align,
                name=None,
            )

            md_lines = self._last_monster_md.splitlines()
            if md_lines and md_lines[0].startswith("## "):
                md_lines[0] = f"## {mon.name}"
            self._last_monster_name = mon.name
            self._last_monster_md = "\n".join(md_lines)
            self.out.setPlainText(self._last_monster_md)

            self.ctx.log(f"[MonsterGen] Reskinned name → {mon.name}")
        except Exception as e:
            self.ctx.log(f"[MonsterGen] ERROR reskinning: {e}")

    def on_send_scratchpad(self):
        try:
            if not self._last_monster_md:
                self.ctx.log("[MonsterGen] Nothing to send — generate first.")
                return

            tags = ["Monster", "MonsterGen"]
            tags.append(f"CR:{self.cr_combo.currentText()}")
            tags.append(f"Type:{self.type_combo.currentText()}")
            tags.append(f"Role:{self.role_combo.currentText()}")

            extra = self.tags_edit.text().strip()
            if extra:
                tags.extend([t.strip() for t in extra.split(",") if t.strip()])

            self.ctx.scratchpad_add(text=self._last_monster_md, tags=tags)
            self.ctx.log(f"[MonsterGen] Sent to Scratchpad: {self._last_monster_name} (tags: {', '.join(tags)})")
        except Exception as e:
            self.ctx.log(f"[MonsterGen] ERROR sending to scratchpad: {e}")

    def on_export(self):
        try:
            if not self._last_monster_md:
                self.ctx.log("[MonsterGen] Nothing to export — generate first.")
                return

            target_cr = parse_cr_label(self.cr_combo.currentText())
            role = self.role_combo.currentText()
            ctype = self.type_combo.currentText()
            size = self.size_combo.currentText()
            align = self.alignment_combo.currentText()
            name = self.name_edit.text().strip() or None

            rng, iteration = self._derive_rng()
            mon = generate_monster(
                rng=rng,
                target_cr=target_cr,
                role=role,
                creature_type=ctype,
                size=size,
                alignment=align,
                name=name if name else None
            )

            pack_dir = export_monster_session_pack(self.ctx, mon, seed_used=iteration)
            self.ctx.log(f"[MonsterGen] Exported session pack: {pack_dir}")
        except Exception as e:
            self.ctx.log(f"[MonsterGen] ERROR exporting: {e}")
