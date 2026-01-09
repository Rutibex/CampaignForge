from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSpinBox, QComboBox, QTextEdit, QGroupBox, QListWidget,
    QListWidgetItem, QLineEdit, QSplitter, QApplication
)
from PySide6.QtCore import Qt

from .generator import (
    NpcGenConfig,
    CULTURE_PACKS,
    list_roles,
    generate_roster,
    npc_to_markdown,
    npc_roster_to_markdown,
    POWER_TIERS,
)
from .exports import export_npc_markdown


class NpcGenWidget(QWidget):
    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx

        self._roster = {
            "version": 1,
            "meta": {},
            "npcs": [],
            "relationships": [],
        }
        self._gen_count = 0
        self._selected_index = -1

        # ---------------- Controls ----------------
        self.culture = QComboBox()
        self.culture.addItems(sorted(CULTURE_PACKS.keys()))

        self.role = QComboBox()
        self.role.addItems(list_roles())

        self.power = QComboBox()
        self.power.addItems(list(POWER_TIERS))

        self.faction = QLineEdit()
        self.faction.setPlaceholderText("Optional (e.g., Red Knives, City Watch)")

        self.count = QSpinBox()
        self.count.setRange(1, 200)
        self.count.setValue(8)

        self.rel_density = QSpinBox()
        self.rel_density.setRange(0, 100)
        self.rel_density.setValue(35)

        self.max_rels = QSpinBox()
        self.max_rels.setRange(0, 12)
        self.max_rels.setValue(3)

        self.generate_btn = QPushButton("Generate")
        self.send_selected_btn = QPushButton("Send Selected")
        self.send_all_btn = QPushButton("Send All")
        self.export_md_btn = QPushButton("Export npc.md")
        self.copy_btn = QPushButton("Copy NPC")

        self.send_selected_btn.setEnabled(False)
        self.send_all_btn.setEnabled(False)
        self.export_md_btn.setEnabled(False)
        self.copy_btn.setEnabled(False)

        # ---------------- Views ----------------
        self.npc_list = QListWidget()
        self.npc_list.setMinimumWidth(240)

        self.detail = QTextEdit()
        self.detail.setReadOnly(True)
        self.detail.setPlaceholderText("Generate NPCs to see details...")

        # ---------------- Layout ----------------
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)

        controls_box = QGroupBox("Settings")
        controls = QVBoxLayout(controls_box)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Culture:"))
        row1.addWidget(self.culture, stretch=1)
        row1.addWidget(QLabel("Role:"))
        row1.addWidget(self.role)
        row1.addWidget(QLabel("Power:"))
        row1.addWidget(self.power)
        row1.addWidget(QLabel("Count:"))
        row1.addWidget(self.count)
        controls.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Faction:"))
        row2.addWidget(self.faction, stretch=1)
        row2.addWidget(QLabel("Rel. Density %:"))
        row2.addWidget(self.rel_density)
        row2.addWidget(QLabel("Max/NPC:"))
        row2.addWidget(self.max_rels)
        controls.addLayout(row2)

        row3 = QHBoxLayout()
        row3.addStretch(1)
        row3.addWidget(self.generate_btn)
        row3.addWidget(self.copy_btn)
        row3.addWidget(self.send_selected_btn)
        row3.addWidget(self.send_all_btn)
        row3.addWidget(self.export_md_btn)
        controls.addLayout(row3)

        root.addWidget(controls_box)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self.npc_list)
        splitter.addWidget(self.detail)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([260, 740])
        root.addWidget(splitter, stretch=1)

        # ---------------- Signals ----------------
        self.generate_btn.clicked.connect(self.on_generate)
        self.export_md_btn.clicked.connect(self.on_export_md)
        self.send_selected_btn.clicked.connect(self.on_send_selected)
        self.send_all_btn.clicked.connect(self.on_send_all)
        self.copy_btn.clicked.connect(self.on_copy_selected)
        self.npc_list.currentRowChanged.connect(self.on_select)

    # ---------------- Actions ----------------

    def on_generate(self):
        self._gen_count += 1

        cfg = NpcGenConfig(
            culture=self.culture.currentText(),
            role=self.role.currentText(),
            faction=(self.faction.text() or "").strip(),
            count=int(self.count.value()),
            power=self.power.currentText(),
            relationship_density=float(self.rel_density.value()) / 100.0,
            max_relationships_per_npc=int(self.max_rels.value()),
        )

        # Deterministic per-click RNG (stable across restarts)
        rng = self.ctx.derive_rng("npcgen", "generate", self._gen_count, cfg.culture, cfg.role, cfg.faction, cfg.count, cfg.power)
        roster = generate_roster(cfg, rng=rng)
        self._roster = roster

        self._populate_list()
        self._update_detail_for_index(0 if roster.get("npcs") else -1)

        self.send_all_btn.setEnabled(len(roster.get("npcs", [])) > 0)
        self.export_md_btn.setEnabled(len(roster.get("npcs", [])) > 0)

        self.ctx.log(
            f"[NPCGen] Generated {len(roster.get('npcs', []))} NPCs (culture={cfg.culture}, role={cfg.role}, faction={cfg.faction or '—'}, rel_density={int(cfg.relationship_density*100)}%)."
        )

    def on_select(self, row: int):
        self._update_detail_for_index(row)

    def on_copy_selected(self):
        idx = self.npc_list.currentRow()
        if idx < 0 or idx >= len(self._roster.get("npcs", [])):
            return
        npc = self._roster["npcs"][idx]
        md = npc_to_markdown(npc)
        QApplication.clipboard().setText(md)
        self.ctx.log(f"[NPCGen] Copied NPC markdown to clipboard: {npc.get('name','(unknown)')}")

    def on_send_selected(self):
        idx = self.npc_list.currentRow()
        if idx < 0 or idx >= len(self._roster.get("npcs", [])):
            return
        npc = self._roster["npcs"][idx]
        self._send_npc_to_scratchpad(npc)

    def on_send_all(self):
        npcs = self._roster.get("npcs", [])
        if not npcs:
            return
        # Roster-level note is often more useful than many small ones
        md = npc_roster_to_markdown(self._roster, title="NPC Roster")

        tags = ["NPC", "NPC:Roster"]
        faction = (self.faction.text() or "").strip()
        if faction:
            tags.append(f"Faction:{faction}")

        self.ctx.scratchpad_add(md, tags=tags)
        self.ctx.log(f"[NPCGen] Sent roster to scratchpad ({len(npcs)} NPCs).")

    def on_export_md(self):
        npcs = self._roster.get("npcs", [])
        if not npcs:
            return
        seed = self._roster.get("meta", {}).get("seed")
        p = export_npc_markdown(self.ctx, self._roster, title="NPC Roster", seed=seed)
        self.ctx.log(f"[NPCGen] Exported npc.md: {p}")

    # ---------------- Helpers ----------------

    def _send_npc_to_scratchpad(self, npc: dict):
        name = npc.get("name", "Unknown")
        tags = ["NPC", f"NPC:{name}"]
        faction = npc.get("faction") or ""
        if faction:
            tags.append(f"Faction:{faction}")
        # Extra quick tags
        role = npc.get("role")
        if role:
            tags.append(f"Role:{role}")
        culture = npc.get("culture")
        if culture:
            tags.append(f"Culture:{culture}")

        md = npc_to_markdown(npc)
        self.ctx.scratchpad_add(md, tags=tags)
        self.ctx.log(f"[NPCGen] Sent NPC to scratchpad: {name}")

    def _populate_list(self):
        self.npc_list.blockSignals(True)
        self.npc_list.clear()
        for npc in self._roster.get("npcs", []):
            name = npc.get("name", "(unnamed)")
            role = npc.get("role", "")
            faction = npc.get("faction", "")
            label = name
            if role:
                label += f" — {role}"
            if faction:
                label += f" ({faction})"
            self.npc_list.addItem(QListWidgetItem(label))
        self.npc_list.blockSignals(False)

        if self.npc_list.count() > 0:
            self.npc_list.setCurrentRow(0)
            self.send_selected_btn.setEnabled(True)
            self.copy_btn.setEnabled(True)
        else:
            self.send_selected_btn.setEnabled(False)
            self.copy_btn.setEnabled(False)

    def _update_detail_for_index(self, idx: int):
        npcs = self._roster.get("npcs", [])
        if idx < 0 or idx >= len(npcs):
            self.detail.setPlainText("")
            self.send_selected_btn.setEnabled(False)
            self.copy_btn.setEnabled(False)
            return

        npc = npcs[idx]
        md = npc_to_markdown(npc, roster=self._roster)
        self.detail.setMarkdown(md)
        self.send_selected_btn.setEnabled(True)
        self.copy_btn.setEnabled(True)

    # ---------------- Persistence ----------------

    def serialize_state(self) -> dict:
        return {
            "version": 1,
            "ui": {
                "culture": int(self.culture.currentIndex()),
                "role": int(self.role.currentIndex()),
                "power": int(self.power.currentIndex()),
                "faction": (self.faction.text() or ""),
                "count": int(self.count.value()),
                "rel_density": int(self.rel_density.value()),
                "max_rels": int(self.max_rels.value()),
            },
            "data": {
                "gen_count": int(self._gen_count),
                "roster": self._roster,
            },
        }

    def load_state(self, state: dict) -> None:
        state = state or {}
        ui = state.get("ui", {})

        try:
            self.culture.setCurrentIndex(int(ui.get("culture", self.culture.currentIndex())))
        except Exception:
            pass
        try:
            self.role.setCurrentIndex(int(ui.get("role", self.role.currentIndex())))
        except Exception:
            pass
        try:
            self.power.setCurrentIndex(int(ui.get("power", self.power.currentIndex())))
        except Exception:
            pass
        try:
            self.faction.setText(str(ui.get("faction", self.faction.text() or "")))
        except Exception:
            pass
        try:
            self.count.setValue(int(ui.get("count", self.count.value())))
        except Exception:
            pass
        try:
            self.rel_density.setValue(int(ui.get("rel_density", self.rel_density.value())))
        except Exception:
            pass
        try:
            self.max_rels.setValue(int(ui.get("max_rels", self.max_rels.value())))
        except Exception:
            pass

        data = state.get("data", {})
        try:
            self._gen_count = int(data.get("gen_count", self._gen_count))
        except Exception:
            pass

        roster = data.get("roster")
        if isinstance(roster, dict) and roster.get("npcs"):
            self._roster = roster
            self._populate_list()
            self._update_detail_for_index(0)
            self.send_all_btn.setEnabled(True)
            self.export_md_btn.setEnabled(True)
        else:
            self._roster = {"version": 1, "meta": {}, "npcs": [], "relationships": []}
            self.send_all_btn.setEnabled(False)
            self.export_md_btn.setEnabled(False)
