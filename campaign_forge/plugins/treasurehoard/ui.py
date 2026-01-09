from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QSpinBox, QCheckBox, QTextEdit, QGroupBox, QTabWidget,
    QLineEdit, QApplication, QMessageBox
)

from .generator import (
    HoardConfig, generate_hoard, load_tables, SCALES, OWNER_TYPES, INTENTS, AGES, MAGIC_DENSITIES
)
from .exports import hoard_to_markdown, write_session_pack


class TreasureHoardWidget(QWidget):
    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx
        self.plugin_id = "treasurehoard"
        self._tables = load_tables(Path(__file__).resolve().parent)

        self._generate_count = 0
        self._last_hoard: Optional[Dict[str, Any]] = None
        self._last_seed: Optional[int] = None

        # --- controls ---
        self.scale = QComboBox()
        self.scale.addItems([s for s, _ in SCALES])
        self.scale.setCurrentText("Dungeon Cache")

        self.owner = QComboBox()
        self.owner.addItems(OWNER_TYPES)
        self.owner.setCurrentText("Goblin-kind / Humanoids (poor)")

        self.intent = QComboBox()
        self.intent.addItems(INTENTS)
        self.intent.setCurrentText("Hidden cache")

        self.age = QComboBox()
        self.age.addItems(AGES)
        self.age.setCurrentText("Old")

        self.culture = QLineEdit()
        self.culture.setPlaceholderText("Local / dwarven / imperial / etc.")
        self.culture.setText("Local")

        self.richness = QSpinBox()
        self.richness.setRange(0, 100)
        self.richness.setValue(50)

        self.danger = QSpinBox()
        self.danger.setRange(0, 100)
        self.danger.setValue(50)

        self.magic_density = QComboBox()
        self.magic_density.addItems(MAGIC_DENSITIES)
        self.magic_density.setCurrentText("Standard")

        # include toggles
        self.inc_coins = QCheckBox("Coins (CP/SP/EP/GP/PP)")
        self.inc_gems = QCheckBox("Gems & Jewels")
        self.inc_art = QCheckBox("Art Objects")
        self.inc_comm = QCheckBox("Commodities")
        self.inc_magic = QCheckBox("Magic Items")
        self.inc_scrolls = QCheckBox("Scrolls")
        self.inc_relics = QCheckBox("Relics / Symbols")
        self.inc_comp = QCheckBox("Complications & Hooks")

        for cb in [self.inc_coins, self.inc_gems, self.inc_art, self.inc_comm, self.inc_magic, self.inc_scrolls, self.inc_relics, self.inc_comp]:
            cb.setChecked(True)

        self.track_weight = QCheckBox("Estimate weight & bulk (OSR-friendly)")
        self.track_weight.setChecked(True)

        self.liquidation = QCheckBox("Include liquidation notes")
        self.liquidation.setChecked(True)

        # buttons
        self.generate_btn = QPushButton("Generate")
        self.copy_btn = QPushButton("Copy Markdown")
        self.copy_btn.setEnabled(False)

        self.send_btn = QPushButton("Send to Scratchpad")
        self.send_btn.setEnabled(False)

        self.export_btn = QPushButton("Export Session Pack")
        self.export_btn.setEnabled(False)

        # outputs
        self.tabs = QTabWidget()
        self.md_out = QTextEdit()
        self.md_out.setPlaceholderText("Generated hoard Markdown will appear here…")
        self.md_out.setLineWrapMode(QTextEdit.NoWrap)

        self.json_out = QTextEdit()
        self.json_out.setPlaceholderText("JSON output will appear here…")
        self.json_out.setLineWrapMode(QTextEdit.NoWrap)

        self.tabs.addTab(self.md_out, "Summary (Markdown)")
        self.tabs.addTab(self.json_out, "Raw JSON")

        # --- layout ---
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)

        box = QGroupBox("Hoard Parameters")
        lay = QVBoxLayout(box)

        r1 = QHBoxLayout()
        r1.addWidget(QLabel("Scale:"))
        r1.addWidget(self.scale, stretch=1)
        r1.addWidget(QLabel("Owner:"))
        r1.addWidget(self.owner, stretch=2)
        lay.addLayout(r1)

        r2 = QHBoxLayout()
        r2.addWidget(QLabel("Intent:"))
        r2.addWidget(self.intent, stretch=2)
        r2.addWidget(QLabel("Age:"))
        r2.addWidget(self.age, stretch=1)
        lay.addLayout(r2)

        r3 = QHBoxLayout()
        r3.addWidget(QLabel("Culture:"))
        r3.addWidget(self.culture, stretch=2)
        r3.addWidget(QLabel("Magic:"))
        r3.addWidget(self.magic_density, stretch=1)
        lay.addLayout(r3)

        r4 = QHBoxLayout()
        r4.addWidget(QLabel("Richness:"))
        r4.addWidget(self.richness)
        r4.addWidget(QLabel("Danger:"))
        r4.addWidget(self.danger)
        r4.addStretch(1)
        lay.addLayout(r4)

        box2 = QGroupBox("Include")
        lay2 = QVBoxLayout(box2)
        rowA = QHBoxLayout()
        rowA.addWidget(self.inc_coins)
        rowA.addWidget(self.inc_gems)
        rowA.addWidget(self.inc_art)
        rowA.addStretch(1)
        lay2.addLayout(rowA)

        rowB = QHBoxLayout()
        rowB.addWidget(self.inc_comm)
        rowB.addWidget(self.inc_magic)
        rowB.addWidget(self.inc_scrolls)
        rowB.addStretch(1)
        lay2.addLayout(rowB)

        rowC = QHBoxLayout()
        rowC.addWidget(self.inc_relics)
        rowC.addWidget(self.inc_comp)
        rowC.addStretch(1)
        lay2.addLayout(rowC)

        box3 = QGroupBox("Options")
        lay3 = QVBoxLayout(box3)
        rowO = QHBoxLayout()
        rowO.addWidget(self.track_weight)
        rowO.addWidget(self.liquidation)
        rowO.addStretch(1)
        lay3.addLayout(rowO)

        actions = QHBoxLayout()
        actions.addStretch(1)
        actions.addWidget(self.generate_btn)
        actions.addWidget(self.copy_btn)
        actions.addWidget(self.send_btn)
        actions.addWidget(self.export_btn)

        root.addWidget(box)
        root.addWidget(box2)
        root.addWidget(box3)
        root.addLayout(actions)
        root.addWidget(self.tabs, stretch=1)

        # signals
        self.generate_btn.clicked.connect(self.on_generate)
        self.copy_btn.clicked.connect(self.on_copy)
        self.send_btn.clicked.connect(self.on_send)
        self.export_btn.clicked.connect(self.on_export)

    def _build_cfg(self) -> HoardConfig:
        return HoardConfig(
            scale=self.scale.currentText(),
            owner_type=self.owner.currentText(),
            intent=self.intent.currentText(),
            age=self.age.currentText(),
            culture=(self.culture.text().strip() or "Local"),
            richness=int(self.richness.value()),
            danger=int(self.danger.value()),
            magic_density=self.magic_density.currentText(),
            include_coins=self.inc_coins.isChecked(),
            include_gems=self.inc_gems.isChecked(),
            include_art=self.inc_art.isChecked(),
            include_commodities=self.inc_comm.isChecked(),
            include_magic_items=self.inc_magic.isChecked(),
            include_scrolls=self.inc_scrolls.isChecked(),
            include_relics=self.inc_relics.isChecked(),
            include_complications=self.inc_comp.isChecked(),
            track_weight=self.track_weight.isChecked(),
            include_liquidation_notes=self.liquidation.isChecked(),
        )

    def on_generate(self) -> None:
        self._generate_count += 1
        cfg = self._build_cfg()

        # Deterministic RNG for each click (reproducible)
        seed = self.ctx.derive_seed(self.plugin_id, "generate", self._generate_count, cfg.scale, cfg.owner_type, cfg.intent, cfg.age, cfg.culture, cfg.richness, cfg.danger, cfg.magic_density)
        rng = self.ctx.derive_rng(seed)

        try:
            hoard_obj = generate_hoard(cfg, rng=rng, tables=self._tables, seed=seed)
            hoard = hoard_obj.__dict__  # dataclass to dict
        except Exception as e:
            self.ctx.log(f"[TreasureHoard] Generation failed: {e}")
            QMessageBox.warning(self, "Treasure Hoard", f"Generation failed:\n{e}")
            return

        md = hoard_to_markdown(hoard)

        self._last_hoard = hoard
        self._last_seed = seed
        self.md_out.setPlainText(md)
        import json
        self.json_out.setPlainText(json.dumps(hoard, indent=2, ensure_ascii=False))

        self.copy_btn.setEnabled(True)
        self.send_btn.setEnabled(True)
        self.export_btn.setEnabled(True)

        gp_target = int(hoard.get("totals", {}).get("gp_target", 0))
        gp_est = int(hoard.get("totals", {}).get("gp_estimated", 0))
        self.ctx.log(f"[TreasureHoard] Generated {cfg.scale} hoard (seed={seed}, target~{gp_target}gp, est~{gp_est}gp).")

    def on_copy(self) -> None:
        text = self.md_out.toPlainText().strip()
        if not text:
            return
        QApplication.clipboard().setText(text)
        self.ctx.log("[TreasureHoard] Copied markdown to clipboard.")

    def on_send(self) -> None:
        if not self._last_hoard:
            return
        text = self.md_out.toPlainText().strip()
        if not text:
            return
        cfg = self._last_hoard.get("config", {})
        tags = ["Treasure", "Hoard", f"Scale:{cfg.get('scale','')}", f"Owner:{cfg.get('owner_type','')}"]
        self.ctx.scratchpad_add(text, tags=tags)
        self.ctx.log("[TreasureHoard] Sent hoard summary to scratchpad.")

    def on_export(self) -> None:
        if not self._last_hoard:
            return
        try:
            pack_dir = write_session_pack(self.ctx, self._last_hoard, title="treasure_hoard")
            self.ctx.log(f"[TreasureHoard] Exported session pack: {pack_dir}")
        except Exception as e:
            self.ctx.log(f"[TreasureHoard] Export failed: {e}")
            QMessageBox.warning(self, "Treasure Hoard", f"Export failed:\n{e}")

    def serialize_state(self) -> dict:
        return {
            "version": 1,
            "generate_count": int(self._generate_count),
            "scale": self.scale.currentText(),
            "owner": self.owner.currentText(),
            "intent": self.intent.currentText(),
            "age": self.age.currentText(),
            "culture": self.culture.text(),
            "richness": int(self.richness.value()),
            "danger": int(self.danger.value()),
            "magic_density": self.magic_density.currentText(),
            "inc": {
                "coins": bool(self.inc_coins.isChecked()),
                "gems": bool(self.inc_gems.isChecked()),
                "art": bool(self.inc_art.isChecked()),
                "commodities": bool(self.inc_comm.isChecked()),
                "magic": bool(self.inc_magic.isChecked()),
                "scrolls": bool(self.inc_scrolls.isChecked()),
                "relics": bool(self.inc_relics.isChecked()),
                "comp": bool(self.inc_comp.isChecked()),
            },
            "opts": {
                "track_weight": bool(self.track_weight.isChecked()),
                "liquidation": bool(self.liquidation.isChecked()),
            },
            "last_markdown": self.md_out.toPlainText(),
        }

    def load_state(self, state: dict) -> None:
        state = state or {}
        ver = int(state.get("version", 1))
        if ver != 1:
            return
        try: self._generate_count = int(state.get("generate_count", self._generate_count))
        except Exception: pass

        # restore dropdowns by text if possible
        def set_combo_text(combo: QComboBox, text: str):
            if not text:
                return
            idx = combo.findText(text)
            if idx >= 0:
                combo.setCurrentIndex(idx)

        set_combo_text(self.scale, state.get("scale", ""))
        set_combo_text(self.owner, state.get("owner", ""))
        set_combo_text(self.intent, state.get("intent", ""))
        set_combo_text(self.age, state.get("age", ""))
        set_combo_text(self.magic_density, state.get("magic_density", ""))

        try: self.culture.setText(str(state.get("culture", self.culture.text())))
        except Exception: pass
        try: self.richness.setValue(int(state.get("richness", self.richness.value())))
        except Exception: pass
        try: self.danger.setValue(int(state.get("danger", self.danger.value())))
        except Exception: pass

        inc = state.get("inc", {}) or {}
        try: self.inc_coins.setChecked(bool(inc.get("coins", self.inc_coins.isChecked())))
        except Exception: pass
        try: self.inc_gems.setChecked(bool(inc.get("gems", self.inc_gems.isChecked())))
        except Exception: pass
        try: self.inc_art.setChecked(bool(inc.get("art", self.inc_art.isChecked())))
        except Exception: pass
        try: self.inc_comm.setChecked(bool(inc.get("commodities", self.inc_comm.isChecked())))
        except Exception: pass
        try: self.inc_magic.setChecked(bool(inc.get("magic", self.inc_magic.isChecked())))
        except Exception: pass
        try: self.inc_scrolls.setChecked(bool(inc.get("scrolls", self.inc_scrolls.isChecked())))
        except Exception: pass
        try: self.inc_relics.setChecked(bool(inc.get("relics", self.inc_relics.isChecked())))
        except Exception: pass
        try: self.inc_comp.setChecked(bool(inc.get("comp", self.inc_comp.isChecked())))
        except Exception: pass

        opts = state.get("opts", {}) or {}
        try: self.track_weight.setChecked(bool(opts.get("track_weight", self.track_weight.isChecked())))
        except Exception: pass
        try: self.liquidation.setChecked(bool(opts.get("liquidation", self.liquidation.isChecked())))
        except Exception: pass

        # restore last output (optional)
        last_md = (state.get("last_markdown") or "").strip()
        if last_md:
            self.md_out.setPlainText(last_md)
            self.copy_btn.setEnabled(True)
            self.send_btn.setEnabled(True)
