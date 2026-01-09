from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTextEdit,
    QComboBox, QCheckBox, QSpinBox, QGroupBox, QTabWidget, QFormLayout, QMessageBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from .generator import ArtifactGenConfig, TIERS, generate_artifact, artifact_to_markdown
from .exports import export_session_pack


class ArtifactWidget(QWidget):
    PLUGIN_ID = "artifacts"

    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx

        self.generate_count = 0
        self.last_artifact = None  # dict

        self._build_ui()

    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)

        # ----- left controls -----
        left = QVBoxLayout()
        left.setSpacing(10)

        title = QLabel("Artifact / Relic Generator")
        f = QFont()
        f.setPointSize(11)
        f.setBold(True)
        title.setFont(f)
        left.addWidget(title)

        # Seed controls
        seed_box = QGroupBox("Seed")
        seed_form = QFormLayout(seed_box)
        self.use_project_seed = QCheckBox("Use project master seed")
        self.use_project_seed.setChecked(True)
        self.seed_spin = QSpinBox()
        self.seed_spin.setRange(0, 2_147_483_647)
        self.seed_spin.setValue(1337)
        seed_form.addRow(self.use_project_seed)
        seed_form.addRow("Override seed", self.seed_spin)
        left.addWidget(seed_box)

        # Config
        cfg_box = QGroupBox("Generation")
        cfg_form = QFormLayout(cfg_box)

        self.tier = QComboBox()
        for t in TIERS:
            self.tier.addItem(t)
        self.tier.setCurrentText("Major Artifact")

        self.theme = QComboBox()
        self.theme.addItem("Random")
        # Load themes from generator table cache via a small hack: call generate once? better: import table
        try:
            from .generator import table
            for th in (table("themes") or []):
                self.theme.addItem(str(th))
        except Exception:
            pass

        self.include_sentience = QCheckBox("Include sentience (Major/Mythic)")
        self.include_sentience.setChecked(True)

        self.fixed_dc = QCheckBox("Use fixed DC (recommended)")
        self.fixed_dc.setChecked(True)

        self.base_dc = QSpinBox()
        self.base_dc.setRange(8, 25)
        self.base_dc.setValue(17)

        self.ability_mod = QComboBox()
        for a in ["Charisma", "Wisdom", "Intelligence"]:
            self.ability_mod.addItem(a)

        self.num_minor = QSpinBox()
        self.num_minor.setRange(0, 8)
        self.num_minor.setValue(3)

        self.num_major = QSpinBox()
        self.num_major.setRange(0, 6)
        self.num_major.setValue(2)

        self.include_drawback = QCheckBox("Include drawback")
        self.include_drawback.setChecked(True)

        self.include_destruction = QCheckBox("Include destruction condition")
        self.include_destruction.setChecked(True)

        self.include_awakening = QCheckBox("Include awakening stage")
        self.include_awakening.setChecked(True)

        cfg_form.addRow("Tier", self.tier)
        cfg_form.addRow("Theme", self.theme)
        cfg_form.addRow(self.include_sentience)
        cfg_form.addRow(self.fixed_dc)
        cfg_form.addRow("Base DC", self.base_dc)
        cfg_form.addRow("DC ability (if formula)", self.ability_mod)
        cfg_form.addRow("Minor properties", self.num_minor)
        cfg_form.addRow("Major powers", self.num_major)
        cfg_form.addRow(self.include_drawback)
        cfg_form.addRow(self.include_destruction)
        cfg_form.addRow(self.include_awakening)

        left.addWidget(cfg_box)

        # Buttons
        btn_row = QHBoxLayout()
        self.btn_generate = QPushButton("Generate")
        self.btn_generate.clicked.connect(self.on_generate)
        self.btn_export = QPushButton("Export Session Pack")
        self.btn_export.clicked.connect(self.on_export)
        btn_row.addWidget(self.btn_generate)
        btn_row.addWidget(self.btn_export)
        left.addLayout(btn_row)

        btn_row2 = QHBoxLayout()
        self.btn_copy_gm = QPushButton("Copy GM")
        self.btn_copy_gm.clicked.connect(lambda: self._copy(which="gm"))
        self.btn_copy_player = QPushButton("Copy Player")
        self.btn_copy_player.clicked.connect(lambda: self._copy(which="player"))
        btn_row2.addWidget(self.btn_copy_gm)
        btn_row2.addWidget(self.btn_copy_player)
        left.addLayout(btn_row2)

        btn_row3 = QHBoxLayout()
        self.btn_send_gm = QPushButton("Send GM → Scratchpad")
        self.btn_send_gm.clicked.connect(lambda: self._send(which="gm"))
        self.btn_send_player = QPushButton("Send Player → Scratchpad")
        self.btn_send_player.clicked.connect(lambda: self._send(which="player"))
        btn_row3.addWidget(self.btn_send_gm)
        btn_row3.addWidget(self.btn_send_player)
        left.addLayout(btn_row3)

        left.addStretch(1)

        # ----- right output -----
        right = QVBoxLayout()
        self.tabs = QTabWidget()

        self.out_gm = QTextEdit()
        self.out_gm.setPlaceholderText("Generate an artifact to see the GM write-up…")
        self.out_player = QTextEdit()
        self.out_player.setPlaceholderText("Generate an artifact to see the player handout…")

        self.tabs.addTab(self.out_gm, "GM")
        self.tabs.addTab(self.out_player, "Player Handout")

        right.addWidget(self.tabs)

        root.addLayout(left, 1)
        root.addLayout(right, 2)

    def _cfg(self) -> ArtifactGenConfig:
        return ArtifactGenConfig(
            tier=str(self.tier.currentText()),
            theme=str(self.theme.currentText()),
            include_sentience=bool(self.include_sentience.isChecked()),
            fixed_dc=bool(self.fixed_dc.isChecked()),
            base_dc=int(self.base_dc.value()),
            ability_mod=str(self.ability_mod.currentText()),
            num_minor=int(self.num_minor.value()),
            num_major=int(self.num_major.value()),
            include_drawback=bool(self.include_drawback.isChecked()),
            include_destruction=bool(self.include_destruction.isChecked()),
            include_awakening=bool(self.include_awakening.isChecked()),
        )

    def _seed(self) -> int:
        if self.use_project_seed.isChecked():
            try:
                return int(getattr(self.ctx, "master_seed", 1337))
            except Exception:
                return 1337
        return int(self.seed_spin.value())

    def on_generate(self):
        try:
            seed = self._seed()
            cfg = self._cfg()
            rng = self.ctx.derive_rng(seed, self.PLUGIN_ID, "generate", int(self.generate_count))
            art = generate_artifact(rng=rng, cfg=cfg)
            art['_provenance'] = {'seed': seed, 'iteration': int(self.generate_count), 'plugin': self.PLUGIN_ID}
            self.last_artifact = art
            self.generate_count += 1

            self.out_gm.setPlainText(artifact_to_markdown(art, for_players=False))
            self.out_player.setPlainText(artifact_to_markdown(art, for_players=True))

            self.ctx.log(f"[Artifacts] Generated: {art.get('name','(unnamed)')} — {art.get('tier','')} / theme {art.get('theme','')} (iter {self.generate_count})")
        except Exception as e:
            self.ctx.log(f"[Artifacts] Generate failed: {e}")
            QMessageBox.warning(self, "Artifact Generator Error", f"Generation failed:\n\n{e}")

    def on_export(self):
        if not self.last_artifact:
            QMessageBox.information(self, "Nothing to export", "Generate an artifact first.")
            return
        try:
            pack_dir = export_session_pack(self.ctx, self.last_artifact, slug=self.last_artifact.get("name","artifact"))
            self.ctx.log(f"[Artifacts] Exported session pack: {pack_dir}")
        except Exception as e:
            self.ctx.log(f"[Artifacts] Export failed: {e}")
            QMessageBox.warning(self, "Export Error", f"Export failed:\n\n{e}")

    def _copy(self, which: str):
        if which == "player":
            text = self.out_player.toPlainText().strip()
        else:
            text = self.out_gm.toPlainText().strip()
        if not text:
            return
        QApplication.clipboard().setText(text)
        self.ctx.log(f"[Artifacts] Copied {which} text to clipboard.")

    def _send(self, which: str):
        if which == "player":
            text = self.out_player.toPlainText().strip()
            tags = ["Artifact", "Handout", "Relic"]
        else:
            text = self.out_gm.toPlainText().strip()
            tags = ["Artifact", "GM", "Relic"]
        if not text:
            return
        # add tier/theme tags if we have artifact loaded
        if self.last_artifact:
            tags.append(f"Relic:{self.last_artifact.get('tier','')}")
            tags.append(f"Theme:{self.last_artifact.get('theme','')}")
        self.ctx.scratchpad_add(text, tags=tags)
        self.ctx.log(f"[Artifacts] Sent {which} text to scratchpad.")

    # ---- persistence ----

    def serialize_state(self) -> dict:
        return {
            "version": 1,
            "generate_count": int(self.generate_count),
            "use_project_seed": bool(self.use_project_seed.isChecked()),
            "seed_override": int(self.seed_spin.value()),
            "cfg": {
                "tier": str(self.tier.currentText()),
                "theme": str(self.theme.currentText()),
                "include_sentience": bool(self.include_sentience.isChecked()),
                "fixed_dc": bool(self.fixed_dc.isChecked()),
                "base_dc": int(self.base_dc.value()),
                "ability_mod": str(self.ability_mod.currentText()),
                "num_minor": int(self.num_minor.value()),
                "num_major": int(self.num_major.value()),
                "include_drawback": bool(self.include_drawback.isChecked()),
                "include_destruction": bool(self.include_destruction.isChecked()),
                "include_awakening": bool(self.include_awakening.isChecked()),
            },
            "last_artifact": self.last_artifact,
        }

    def load_state(self, state: dict) -> None:
        state = state or {}
        try:
            self.generate_count = int(state.get("generate_count", 0))
        except Exception:
            self.generate_count = 0

        try:
            self.use_project_seed.setChecked(bool(state.get("use_project_seed", True)))
        except Exception:
            pass
        try:
            self.seed_spin.setValue(int(state.get("seed_override", self.seed_spin.value())))
        except Exception:
            pass

        cfg = (state.get("cfg") or {})
        try: self.tier.setCurrentText(str(cfg.get("tier", self.tier.currentText())))
        except Exception: pass
        try: self.theme.setCurrentText(str(cfg.get("theme", self.theme.currentText())))
        except Exception: pass
        try: self.include_sentience.setChecked(bool(cfg.get("include_sentience", self.include_sentience.isChecked())))
        except Exception: pass
        try: self.fixed_dc.setChecked(bool(cfg.get("fixed_dc", self.fixed_dc.isChecked())))
        except Exception: pass
        try: self.base_dc.setValue(int(cfg.get("base_dc", self.base_dc.value())))
        except Exception: pass
        try: self.ability_mod.setCurrentText(str(cfg.get("ability_mod", self.ability_mod.currentText())))
        except Exception: pass
        try: self.num_minor.setValue(int(cfg.get("num_minor", self.num_minor.value())))
        except Exception: pass
        try: self.num_major.setValue(int(cfg.get("num_major", self.num_major.value())))
        except Exception: pass
        try: self.include_drawback.setChecked(bool(cfg.get("include_drawback", self.include_drawback.isChecked())))
        except Exception: pass
        try: self.include_destruction.setChecked(bool(cfg.get("include_destruction", self.include_destruction.isChecked())))
        except Exception: pass
        try: self.include_awakening.setChecked(bool(cfg.get("include_awakening", self.include_awakening.isChecked())))
        except Exception: pass

        self.last_artifact = state.get("last_artifact", None)
        if self.last_artifact:
            try:
                self.out_gm.setPlainText(artifact_to_markdown(self.last_artifact, for_players=False))
                self.out_player.setPlainText(artifact_to_markdown(self.last_artifact, for_players=True))
            except Exception:
                pass
