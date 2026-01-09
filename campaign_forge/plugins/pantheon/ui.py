from __future__ import annotations

from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QSpinBox, QComboBox, QTextEdit, QSplitter, QListWidget, QListWidgetItem,
    QMessageBox, QCheckBox
)

from .generator import DEFAULT_TABLES, generate_pantheon, pantheon_to_dict, Pantheon
from .exports import export_session_pack


class PantheonWidget(QWidget):
    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx

        self.plugin_id = "pantheon"

        # Generation bookkeeping for reproducibility
        self.generate_count = 0
        self.last_seed_used = None  # int
        self.last_pantheon: Optional[Pantheon] = None

        self._build_ui()

    # -----------------------------
    # UI Construction
    # -----------------------------

    def _build_ui(self):
        root = QVBoxLayout()
        self.setLayout(root)

        header = QLabel("Pantheon Generator — gods, cults, conflicts, and the relationship web")
        header.setStyleSheet("font-weight: 600; font-size: 14px;")
        root.addWidget(header)

        # Controls row 1
        controls = QHBoxLayout()
        root.addLayout(controls)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Pantheon name (e.g., The Court of Ash and Bells)")
        controls.addWidget(QLabel("Name:"))
        controls.addWidget(self.name_edit, 2)

        self.count_spin = QSpinBox()
        self.count_spin.setRange(3, 30)
        self.count_spin.setValue(9)
        controls.addWidget(QLabel("Gods:"))
        controls.addWidget(self.count_spin)

        self.power_curve = QComboBox()
        self.power_curve.addItems(["flat", "tiered"])
        controls.addWidget(QLabel("Power curve:"))
        controls.addWidget(self.power_curve)

        self.tone_combo = QComboBox()
        self.tone_combo.addItems(DEFAULT_TABLES["tones"])
        controls.addWidget(QLabel("Tone:"))
        controls.addWidget(self.tone_combo)

        self.involve_combo = QComboBox()
        self.involve_combo.addItems(DEFAULT_TABLES["involvement"])
        controls.addWidget(QLabel("Involvement:"))
        controls.addWidget(self.involve_combo)

        self.struct_combo = QComboBox()
        self.struct_combo.addItems(DEFAULT_TABLES["structures"])
        controls.addWidget(QLabel("Structure:"))
        controls.addWidget(self.struct_combo)

        # Controls row 2
        controls2 = QHBoxLayout()
        root.addLayout(controls2)

        self.name_style = QComboBox()
        self.name_style.addItems(["Epithet-like", "Classical", "Harsh"])
        controls2.addWidget(QLabel("Name style:"))
        controls2.addWidget(self.name_style)

        self.use_custom_names = QCheckBox("Use custom names (one per line)")
        controls2.addWidget(self.use_custom_names)

        self.generate_btn = QPushButton("Generate Pantheon")
        self.generate_btn.clicked.connect(self.on_generate)
        controls2.addWidget(self.generate_btn)

        self.export_btn = QPushButton("Export Session Pack")
        self.export_btn.clicked.connect(self.on_export)
        self.export_btn.setEnabled(False)
        controls2.addWidget(self.export_btn)

        self.to_scratch_btn = QPushButton("Send Summary to Scratchpad")
        self.to_scratch_btn.clicked.connect(self.on_send_to_scratchpad)
        self.to_scratch_btn.setEnabled(False)
        controls2.addWidget(self.to_scratch_btn)

        controls2.addStretch(1)

        # Splitter
        split = QSplitter(Qt.Horizontal)
        root.addWidget(split, 1)

        left = QWidget()
        left_l = QVBoxLayout()
        left.setLayout(left_l)

        left_l.addWidget(QLabel("Gods"))
        self.god_list = QListWidget()
        self.god_list.currentItemChanged.connect(self.on_select_god)
        left_l.addWidget(self.god_list, 1)

        left_l.addWidget(QLabel("Custom names (optional)"))
        self.custom_names = QTextEdit()
        self.custom_names.setPlaceholderText("One name per line. Only used if checkbox is enabled.")
        self.custom_names.setFixedHeight(120)
        left_l.addWidget(self.custom_names)

        split.addWidget(left)

        right = QWidget()
        right_l = QVBoxLayout()
        right.setLayout(right_l)

        right_l.addWidget(QLabel("Output (overview / selected god / relationships / conflicts)"))
        self.output = QTextEdit()
        self.output.setReadOnly(True)
        right_l.addWidget(self.output, 1)

        split.addWidget(right)
        split.setStretchFactor(0, 0)
        split.setStretchFactor(1, 1)

        self._render_help()

    def _render_help(self):
        self.output.setPlainText(
            "# Pantheon Generator\n\n"
            "Generate a pantheon of gods with overlapping domains, interrelationships, and conflicts.\n\n"
            "Workflow:\n"
            "1) Set name + knobs\n"
            "2) Generate\n"
            "3) Click gods for details\n"
            "4) Export session pack (Markdown + JSON)\n"
            "5) Send summary to scratchpad\n"
        )

    # -----------------------------
    # Generation / selection
    # -----------------------------

    def _get_custom_names(self) -> List[str]:
        txt = self.custom_names.toPlainText().strip()
        if not txt:
            return []
        return [line.strip() for line in txt.splitlines() if line.strip()]

    def on_generate(self):
        try:
            pantheon_name = self.name_edit.text().strip() or "Unnamed Pantheon"
            n = int(self.count_spin.value())

            tone = self.tone_combo.currentText()
            involvement = self.involve_combo.currentText()
            structure = self.struct_combo.currentText()
            power_curve = self.power_curve.currentText()
            name_style = self.name_style.currentText()

            custom_names = self._get_custom_names() if self.use_custom_names.isChecked() else None

            iteration = self.generate_count
            rng = self.ctx.derive_rng(self.ctx.master_seed, self.plugin_id, "generate", iteration)

            pantheon = generate_pantheon(
                rng=rng,
                pantheon_name=pantheon_name,
                count=n,
                tone=tone,
                involvement=involvement,
                structure=structure,
                power_curve=power_curve,
                name_style=name_style,
                custom_names=custom_names
            )

            # If ctx.derive_seed exists, use it; otherwise fall back.
            seed_used = None
            if hasattr(self.ctx, "derive_seed"):
                seed_used = int(self.ctx.derive_seed(self.ctx.master_seed, self.plugin_id, "generate", iteration))
            else:
                seed_used = int(self.ctx.master_seed) + int(iteration)

            pantheon.seed = seed_used
            pantheon.iteration = iteration

            self.last_pantheon = pantheon
            self.last_seed_used = seed_used
            self.generate_count += 1

            self._populate_god_list(pantheon)
            self._render_overview(pantheon)

            self.export_btn.setEnabled(True)
            self.to_scratch_btn.setEnabled(True)

            self.ctx.log(f"[Pantheon] Generated '{pantheon.name}' ({len(pantheon.gods)} gods) seed={seed_used} iter={iteration}")

        except Exception as e:
            self.ctx.log(f"[Pantheon] ERROR during generation: {e}")
            QMessageBox.critical(self, "Pantheon Generator Error", str(e))

    def _populate_god_list(self, p: Pantheon):
        self.god_list.blockSignals(True)
        self.god_list.clear()
        for g in p.gods:
            dom = ", ".join(g.domains_primary + g.domains_secondary)
            item = QListWidgetItem(f"{g.name} — {g.tier} — {dom}")
            item.setData(Qt.UserRole, g.gid)
            self.god_list.addItem(item)
        self.god_list.blockSignals(False)
        if self.god_list.count() > 0:
            self.god_list.setCurrentRow(0)

    def on_select_god(self, current: QListWidgetItem, previous: QListWidgetItem):
        if not self.last_pantheon or not current:
            return
        gid = current.data(Qt.UserRole)
        g = next((x for x in self.last_pantheon.gods if x.gid == gid), None)
        if not g:
            return
        self._render_god_detail(g)

    def _render_overview(self, p: Pantheon):
        lines = []
        lines.append(f"# Pantheon: {p.name}")
        lines.append("")
        lines.append(f"- Tone: {p.tone}")
        lines.append(f"- Involvement: {p.involvement}")
        lines.append(f"- Structure: {p.structure}")
        lines.append(f"- Seed: {p.seed}")
        lines.append(f"- Iteration: {p.iteration}")
        lines.append("")
        lines.append("## Metrics")
        for k, v in p.metrics.items():
            lines.append(f"- {k.replace('_',' ').title()}: {v}")
        lines.append("")
        lines.append("## Gods")
        for g in p.gods:
            dom = ", ".join(g.domains_primary + g.domains_secondary)
            lines.append(f"- **{g.name}** ({g.tier}) — {dom}")
        lines.append("")
        lines.append("## Conflicts")
        if not p.conflicts:
            lines.append("- None detected (or everything is hidden behind masks).")
        else:
            name_by_id = {g.gid: g.name for g in p.gods}
            for c in p.conflicts:
                inv = ", ".join(name_by_id.get(x, x) for x in c.gods_involved)
                lines.append(f"- {c.title} — {inv} (impact {c.stability_impact}/5)")
        lines.append("")
        lines.append("_Select a god on the left for details._")
        self.output.setMarkdown("\n".join(lines))

    def _render_god_detail(self, g):
        p = self.last_pantheon
        if not p:
            return
        name_by_id = {x.gid: x.name for x in p.gods}

        rels = [r for r in p.relationships if r.a == g.gid or r.b == g.gid]
        rel_lines = []
        for r in rels:
            other = r.b if r.a == g.gid else r.a
            other_name = name_by_id.get(other, other)
            rel_lines.append(f"- **{other_name}** — {r.rel_type} ({r.intensity}/5, {r.status})")

        conf = [c for c in p.conflicts if g.gid in c.gods_involved]
        conf_lines = []
        for c in conf:
            conf_lines.append(f"- {c.title} (impact {c.stability_impact}/5)")

        md = []
        md.append(f"# {g.name}")
        md.append("")
        md.append(f"**Tier:** {g.tier}")
        md.append(f"**Titles:** {'; '.join(g.titles)}")
        md.append(f"**Epithet:** {g.epithet}")
        md.append("")
        md.append("## Domains")
        md.append(f"- Primary: {', '.join(g.domains_primary) if g.domains_primary else '—'}")
        md.append(f"- Secondary: {', '.join(g.domains_secondary) if g.domains_secondary else '—'}")
        md.append(f"- Forbidden: {', '.join(g.forbidden) if g.forbidden else '—'}")
        md.append("")
        md.append("## Temperament and Motives")
        md.append(f"- Temperament: {g.temperament}")
        md.append(f"- Desire: {g.desire}")
        md.append(f"- Flaw: {g.flaw}")
        md.append(f"- Taboo: {g.taboo}")
        md.append("")
        md.append("## Iconography")
        md.append(f"- Symbol: {g.icon_symbol}")
        md.append(f"- Sacred Animal: {g.icon_animal}")
        md.append(f"- Sacred Material: {g.icon_material}")
        md.append(f"- Holy Day: {g.holy_day}")
        md.append("")
        md.append("## Worship")
        md.append(f"- Style: {g.worship_style}")
        md.append(f"- Offerings: {', '.join(g.offerings)}")
        md.append(f"- Clergy: {g.clergy}")
        md.append("")
        md.append("## Virtues & Vices")
        md.append(f"- Virtues: {', '.join(g.virtues)}")
        md.append(f"- Vices: {', '.join(g.vices)}")
        md.append("")
        md.append("## Myth Fragments")
        md.append(f"- Origin: {g.origin_myth}")
        md.append(f"- Greatest Victory: {g.victory}")
        md.append(f"- Greatest Failure: {g.failure}")
        md.append(f"- Greatest Sin: {g.sin}")
        md.append(f"- What Mortals Believe: {g.mortal_belief}")
        md.append("")
        md.append("## Relationships")
        md.append("\n".join(rel_lines) if rel_lines else "_No recorded ties. (Which is usually a lie.)_")
        md.append("")
        md.append("## Conflicts")
        md.append("\n".join(conf_lines) if conf_lines else "_Not currently named in a major conflict._")

        self.output.setMarkdown("\n".join(md))

    def on_send_to_scratchpad(self):
        if not self.last_pantheon:
            return
        p = self.last_pantheon

        lines = []
        lines.append(f"# Pantheon: {p.name}")
        lines.append("")
        lines.append(f"- Tone: {p.tone} | Involvement: {p.involvement} | Structure: {p.structure}")
        lines.append(f"- Seed: {p.seed} | Iteration: {p.iteration}")
        lines.append("")
        lines.append("## Gods (quick refs)")
        for g in p.gods:
            dom = ", ".join(g.domains_primary + g.domains_secondary)
            lines.append(f"- **{g.name}** ({g.tier}) — {dom} | taboo: *{g.taboo}*")
        lines.append("")
        lines.append("## Active Conflicts")
        if p.conflicts:
            name_by_id = {g.gid: g.name for g in p.gods}
            for c in p.conflicts:
                inv = ", ".join(name_by_id.get(x, x) for x in c.gods_involved)
                lines.append(f"- **{c.title}** — {inv} | Stakes: {c.stakes}")
        else:
            lines.append("- None detected (or they’re masked).")

        tags = ["Pantheon", "Lore", "Religion", f"Pantheon:{p.name}"]
        self.ctx.scratchpad_add("\n".join(lines), tags=tags)
        self.ctx.log(f"[Pantheon] Sent summary to scratchpad: {p.name}")

    def on_export(self):
        if not self.last_pantheon:
            return
        try:
            pack_dir = export_session_pack(self.ctx, self.last_pantheon)
            self.ctx.log(f"[Pantheon] Exported session pack: {pack_dir}")
            QMessageBox.information(self, "Export Complete", f"Exported to:\n{pack_dir}")
        except Exception as e:
            self.ctx.log(f"[Pantheon] Export ERROR: {e}")
            QMessageBox.critical(self, "Export Error", str(e))

    def serialize_state(self) -> dict:
        return {
            "version": 1,
            "ui": {
                "pantheon_name": self.name_edit.text(),
                "count": int(self.count_spin.value()),
                "power_curve": self.power_curve.currentText(),
                "tone": self.tone_combo.currentText(),
                "involvement": self.involve_combo.currentText(),
                "structure": self.struct_combo.currentText(),
                "name_style": self.name_style.currentText(),
                "use_custom_names": bool(self.use_custom_names.isChecked()),
                "custom_names": self.custom_names.toPlainText(),
            },
            "data": {
                "generate_count": int(self.generate_count),
                "last_seed_used": self.last_seed_used,
                "last_pantheon": pantheon_to_dict(self.last_pantheon) if self.last_pantheon else None,
            }
        }

    def load_state(self, state: dict) -> None:
        if not state:
            return
        try:
            ver = state.get("version", 1)
            if ver != 1:
                self.ctx.log(f"[Pantheon] Unknown state version: {ver} (ignoring)")
                return

            ui = state.get("ui", {})
            self.name_edit.setText(ui.get("pantheon_name", ""))
            self.count_spin.setValue(int(ui.get("count", 9)))

            self._set_combo_text(self.power_curve, ui.get("power_curve", "flat"))
            self._set_combo_text(self.tone_combo, ui.get("tone", self.tone_combo.itemText(0)))
            self._set_combo_text(self.involve_combo, ui.get("involvement", self.involve_combo.itemText(0)))
            self._set_combo_text(self.struct_combo, ui.get("structure", self.struct_combo.itemText(0)))
            self._set_combo_text(self.name_style, ui.get("name_style", "Epithet-like"))

            self.use_custom_names.setChecked(bool(ui.get("use_custom_names", False)))
            self.custom_names.setPlainText(ui.get("custom_names", ""))

            data = state.get("data", {})
            self.generate_count = int(data.get("generate_count", 0))
            self.last_seed_used = data.get("last_seed_used", None)

            last_p = data.get("last_pantheon", None)
            if last_p and isinstance(last_p, dict):
                self.last_pantheon = self._rehydrate_pantheon(last_p)
                if self.last_pantheon:
                    self._populate_god_list(self.last_pantheon)
                    self._render_overview(self.last_pantheon)
                    self.export_btn.setEnabled(True)
                    self.to_scratch_btn.setEnabled(True)

        except Exception as e:
            self.ctx.log(f"[Pantheon] load_state ERROR (ignored): {e}")

    def _set_combo_text(self, combo: QComboBox, text: str):
        if not text:
            return
        idx = combo.findText(text)
        if idx >= 0:
            combo.setCurrentIndex(idx)

    def _rehydrate_pantheon(self, d: Dict[str, Any]) -> Optional[Pantheon]:
        try:
            from .generator import God, Relationship, Conflict, Pantheon

            gods = [God(**g) for g in d.get("gods", [])]
            rels = [Relationship(**r) for r in d.get("relationships", [])]
            confs = [Conflict(**c) for c in d.get("conflicts", [])]

            return Pantheon(
                version=int(d.get("version", 1)),
                name=str(d.get("name", "Pantheon")),
                tone=str(d.get("tone", "")),
                involvement=str(d.get("involvement", "")),
                structure=str(d.get("structure", "")),
                seed=int(d.get("seed", 0)),
                iteration=int(d.get("iteration", 0)),
                gods=gods,
                relationships=rels,
                conflicts=confs,
                metrics=dict(d.get("metrics", {})),
            )
        except Exception:
            return None
