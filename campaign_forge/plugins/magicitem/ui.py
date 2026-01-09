from __future__ import annotations

import traceback

# Try common Qt bindings; Campaign Forge is Qt-based, but projects vary.
try:
    from PySide6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
        QComboBox, QCheckBox, QSlider, QTextEdit, QMessageBox, QGroupBox
    )
    from PySide6.QtCore import Qt
except Exception:  # pragma: no cover
    from PyQt5.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
        QComboBox, QCheckBox, QSlider, QTextEdit, QMessageBox, QGroupBox
    )
    from PyQt5.QtCore import Qt

from . import tables
from .generator import generate_magic_item, MagicItem
from .exports import export_magic_item


def _int_slider(minv=0, maxv=100, val=50):
    s = QSlider(Qt.Horizontal)
    s.setMinimum(minv)
    s.setMaximum(maxv)
    s.setValue(val)
    s.setTickInterval(10)
    s.setSingleStep(1)
    return s


class MagicItemWidget(QWidget):
    """
    Magic Item Generator Module
    - deterministic generation via ctx.derive_rng if available
    - scratchpad push + export
    - stateful widget (serialize_state / load_state)
    """

    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx
        self.plugin_id = "magicitem"

        self.generate_count = 0
        self.last_item: MagicItem | None = None
        self.last_seed_used: int = 0

        self._build_ui()

    # ---------- UI ----------

    def _build_ui(self):
        root = QVBoxLayout(self)

        title = QLabel("Magic Item Generator")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        root.addWidget(title)

        # Controls
        controls = QGroupBox("Generation Controls")
        c_layout = QVBoxLayout(controls)

        row1 = QHBoxLayout()
        self.cmb_theme = QComboBox()
        self.cmb_theme.addItem("Any Theme")
        for t in tables.THEMES:
            self.cmb_theme.addItem(t)

        self.cmb_type = QComboBox()
        self.cmb_type.addItem("Any Type")
        for it in tables.ITEM_TYPES:
            self.cmb_type.addItem(it)

        self.cmb_rarity = QComboBox()
        self.cmb_rarity.addItem("Any Rarity")
        for r in tables.RARITIES:
            self.cmb_rarity.addItem(r)

        row1.addWidget(QLabel("Theme:"))
        row1.addWidget(self.cmb_theme, 2)
        row1.addWidget(QLabel("Type:"))
        row1.addWidget(self.cmb_type, 2)
        row1.addWidget(QLabel("Rarity:"))
        row1.addWidget(self.cmb_rarity, 1)
        c_layout.addLayout(row1)

        row2 = QHBoxLayout()
        self.sld_power = _int_slider(val=55)
        self.sld_risk = _int_slider(val=50)
        self.sld_weird = _int_slider(val=55)

        row2.addWidget(QLabel("Power"))
        row2.addWidget(self.sld_power, 2)
        row2.addWidget(QLabel("Risk"))
        row2.addWidget(self.sld_risk, 2)
        row2.addWidget(QLabel("Weirdness"))
        row2.addWidget(self.sld_weird, 2)
        c_layout.addLayout(row2)

        row3 = QHBoxLayout()
        self.chk_curse = QCheckBox("Allow Curses / Harsh Costs")
        self.chk_curse.setChecked(True)
        self.chk_session_pack = QCheckBox("Export as Session Pack")
        self.chk_session_pack.setChecked(True)

        row3.addWidget(self.chk_curse)
        row3.addStretch(1)
        row3.addWidget(self.chk_session_pack)
        c_layout.addLayout(row3)

        root.addWidget(controls)

        # Action buttons
        btn_row = QHBoxLayout()
        self.btn_generate = QPushButton("Generate")
        self.btn_generate.clicked.connect(self.on_generate)

        self.btn_to_scratch = QPushButton("Send to Scratchpad")
        self.btn_to_scratch.clicked.connect(self.on_send_to_scratchpad)

        self.btn_export = QPushButton("Export")
        self.btn_export.clicked.connect(self.on_export)

        btn_row.addWidget(self.btn_generate)
        btn_row.addWidget(self.btn_to_scratch)
        btn_row.addWidget(self.btn_export)
        btn_row.addStretch(1)
        root.addLayout(btn_row)

        # Output preview
        self.txt_preview = QTextEdit()
        self.txt_preview.setReadOnly(True)
        self.txt_preview.setPlaceholderText("Generated item will appear here…")
        root.addWidget(self.txt_preview, 1)

        # Generate an initial item for “instant gratification”
        try:
            self.on_generate()
        except Exception:
            # Silent; should not brick the app.
            pass

    # ---------- RNG helpers ----------

    def _derive_rng_and_seed(self) -> tuple[object, int]:
        """
        Returns (rng, seed_used).
        Prefers ctx.derive_rng(master_seed, plugin_id, action, iteration).
        Falls back to Python's random.Random with derived integer seed.
        """
        master = getattr(self.ctx, "master_seed", 0) or 0
        iteration = self.generate_count

        # Preferred: ctx.derive_rng
        derive = getattr(self.ctx, "derive_rng", None)
        if callable(derive):
            try:
                rng = derive(master, self.plugin_id, "generate", iteration)
                # Try to also compute a stable seed value to display
                # If ctx exposes a stable seed helper, use it; else hash-like derivation.
                seed_used = self._stable_int_seed(master, self.plugin_id, "generate", iteration)
                return rng, seed_used
            except Exception:
                pass

        # Fallback: Random(seed)
        import random
        seed_used = self._stable_int_seed(master, self.plugin_id, "generate", iteration)
        return random.Random(seed_used), seed_used

    @staticmethod
    def _stable_int_seed(master_seed: int, *parts) -> int:
        # Stable, cross-run derivation without Python's randomized hash():
        s = str(master_seed) + "|" + "|".join(map(str, parts))
        # Simple 32-bit FNV-1a style
        h = 2166136261
        for ch in s:
            h ^= ord(ch)
            h = (h * 16777619) & 0xFFFFFFFF
        return int(h)

    # ---------- Actions ----------

    def on_generate(self):
        try:
            self.generate_count += 1
            rng, seed_used = self._derive_rng_and_seed()
            self.last_seed_used = seed_used

            theme = self.cmb_theme.currentText()
            if theme == "Any Theme":
                theme = None

            item_type = self.cmb_type.currentText()
            if item_type == "Any Type":
                item_type = None

            rarity = self.cmb_rarity.currentText()
            if rarity == "Any Rarity":
                rarity = None

            item = generate_magic_item(
                rng,
                theme=theme,
                item_type=item_type,
                rarity=rarity,
                power=int(self.sld_power.value()),
                risk=int(self.sld_risk.value()),
                weirdness=int(self.sld_weird.value()),
                allow_curse=bool(self.chk_curse.isChecked()),
                seed_used=seed_used,
            )
            self.last_item = item
            self.txt_preview.setPlainText(item.to_markdown())

            self._log(f"[MagicItem] Generated: {item.name} (seed {seed_used})")
        except Exception as e:
            self._log(f"[MagicItem] ERROR generating item: {e}")
            self._log(traceback.format_exc())

    def on_send_to_scratchpad(self):
        if not self.last_item:
            return
        try:
            text = self.last_item.to_markdown()
            tags = ["MagicItem", "Treasure", f"Rarity:{self.last_item.rarity}", f"Type:{self.last_item.item_type}"]
            # optional theme tag
            if self.last_item.theme:
                tags.append(f"Theme:{self.last_item.theme}")

            add = getattr(self.ctx, "scratchpad_add", None)
            if callable(add):
                add(text=text, tags=tags)
                self._log(f"[MagicItem] Sent to scratchpad with tags: {', '.join(tags)}")
            else:
                self._log("[MagicItem] Scratchpad service not available on ctx.")
        except Exception as e:
            self._log(f"[MagicItem] ERROR sending to scratchpad: {e}")
            self._log(traceback.format_exc())

    def on_export(self):
        if not self.last_item:
            return
        try:
            pack_dir = export_magic_item(self.ctx, self.last_item, as_session_pack=self.chk_session_pack.isChecked())
            self._log(f"[MagicItem] Exported to: {pack_dir}")
            QMessageBox.information(self, "Export Complete", f"Exported to:\n{pack_dir}")
        except Exception as e:
            self._log(f"[MagicItem] ERROR exporting: {e}")
            self._log(traceback.format_exc())
            QMessageBox.warning(self, "Export Failed", str(e))

    # ---------- Persistence ----------

    def serialize_state(self) -> dict:
        # Store UI knobs + last generated item
        return {
            "version": 1,
            "ui": {
                "theme": self.cmb_theme.currentText(),
                "type": self.cmb_type.currentText(),
                "rarity": self.cmb_rarity.currentText(),
                "power": int(self.sld_power.value()),
                "risk": int(self.sld_risk.value()),
                "weird": int(self.sld_weird.value()),
                "allow_curse": bool(self.chk_curse.isChecked()),
                "session_pack": bool(self.chk_session_pack.isChecked()),
            },
            "data": {
                "generate_count": int(self.generate_count),
                "last_seed_used": int(self.last_seed_used),
                "last_item": (self.last_item.to_dict() if self.last_item else None),
                "last_preview": self.txt_preview.toPlainText(),
            },
        }

    def load_state(self, state: dict) -> None:
        if not state:
            return
        try:
            ver = state.get("version", 1)
            if ver != 1:
                self._log(f"[MagicItem] Unknown state version: {ver} (loading best-effort)")

            ui = state.get("ui", {})
            self._set_combo_text(self.cmb_theme, ui.get("theme", "Any Theme"))
            self._set_combo_text(self.cmb_type, ui.get("type", "Any Type"))
            self._set_combo_text(self.cmb_rarity, ui.get("rarity", "Any Rarity"))

            self.sld_power.setValue(int(ui.get("power", 55)))
            self.sld_risk.setValue(int(ui.get("risk", 50)))
            self.sld_weird.setValue(int(ui.get("weird", 55)))
            self.chk_curse.setChecked(bool(ui.get("allow_curse", True)))
            self.chk_session_pack.setChecked(bool(ui.get("session_pack", True)))

            data = state.get("data", {})
            self.generate_count = int(data.get("generate_count", 0))
            self.last_seed_used = int(data.get("last_seed_used", 0))

            last_preview = data.get("last_preview")
            if isinstance(last_preview, str) and last_preview.strip():
                self.txt_preview.setPlainText(last_preview)

            # Attempt to restore last_item minimally (optional)
            li = data.get("last_item")
            if isinstance(li, dict) and li.get("name"):
                try:
                    self.last_item = MagicItem(**li)
                except Exception:
                    self.last_item = None

        except Exception as e:
            self._log(f"[MagicItem] ERROR loading state: {e}")
            self._log(traceback.format_exc())

    @staticmethod
    def _set_combo_text(combo: QComboBox, text: str):
        if not text:
            return
        idx = combo.findText(text)
        if idx >= 0:
            combo.setCurrentIndex(idx)

    # ---------- Logging ----------

    def _log(self, msg: str):
        log = getattr(self.ctx, "log", None)
        if callable(log):
            log(msg)
        # If no logger exists, we silently do nothing—do not print spam.
