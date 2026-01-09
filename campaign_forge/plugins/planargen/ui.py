# =========================
# campaign_forge/plugins/planargen/ui.py  (PySide6 version)
# =========================
from __future__ import annotations

from typing import Any, Dict

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTextEdit,
    QComboBox, QCheckBox, QGroupBox, QFormLayout, QLineEdit,
    QMessageBox
)

from .generator import (
    CLASSIFICATIONS, TONES,
    generate_plane, plane_to_markdown
)
from .exports import export_plane_markdown


class PlanarGeneratorWidget(QWidget):
    """
    Planar Generator:
    - Ad-lib driven plane dossiers
    - Reproducible generation via ctx.derive_rng(master_seed, plugin_id, "generate", iteration)
    - Lockable identity fields (name / native name / layout)
    - Output to scratchpad + export markdown
    """
    PLUGIN_ID = "planargen"

    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx

        self.generate_count = 0
        self.last_plane = None  # PlaneProfile
        self.last_markdown = ""

        self._build_ui()

    # ---------------------------------------------------------------------
    # UI
    # ---------------------------------------------------------------------
    def _build_ui(self):
        root = QVBoxLayout(self)

        title = QLabel("Planar Generator")
        title.setStyleSheet("font-size: 18px; font-weight: 600;")
        root.addWidget(title)

        controls = QGroupBox("Generation Controls")
        form = QFormLayout(controls)

        self.cmb_class = QComboBox()
        self.cmb_class.addItems(CLASSIFICATIONS)
        if "Conceptual" in CLASSIFICATIONS:
            self.cmb_class.setCurrentText("Conceptual")
        form.addRow("Classification:", self.cmb_class)

        self.cmb_tone = QComboBox()
        self.cmb_tone.addItems(TONES)
        if "Mythic" in TONES:
            self.cmb_tone.setCurrentText("Mythic")
        form.addRow("Tone:", self.cmb_tone)

        self.cmb_depth = QComboBox()
        self.cmb_depth.addItems(["Sketch", "Standard", "Deep"])
        self.cmb_depth.setCurrentText("Standard")
        form.addRow("Detail Level:", self.cmb_depth)

        self.txt_seed = QLineEdit()
        self.txt_seed.setReadOnly(True)
        self._refresh_seed_display()
        form.addRow("Master Seed:", self.txt_seed)

        lock_box = QGroupBox("Locks")
        lock_form = QFormLayout(lock_box)

        self.chk_lock_name = QCheckBox("Lock Plane Name")
        self.chk_lock_native = QCheckBox("Lock Native Name")
        self.chk_lock_layout = QCheckBox("Lock Layout")

        self.txt_locked_name = QLineEdit()
        self.txt_locked_native = QLineEdit()
        self.txt_locked_layout = QLineEdit()

        self.txt_locked_name.setPlaceholderText("Leave blank to let generator choose")
        self.txt_locked_native.setPlaceholderText("Leave blank to let generator choose")
        self.txt_locked_layout.setPlaceholderText("Leave blank to let generator choose")

        lock_form.addRow(self.chk_lock_name, self.txt_locked_name)
        lock_form.addRow(self.chk_lock_native, self.txt_locked_native)
        lock_form.addRow(self.chk_lock_layout, self.txt_locked_layout)

        form.addRow(lock_box)
        root.addWidget(controls)

        btn_row = QHBoxLayout()
        self.btn_generate = QPushButton("Generate Plane")
        self.btn_generate.clicked.connect(self.on_generate)

        self.btn_to_scratchpad = QPushButton("Send to Scratchpad")
        self.btn_to_scratchpad.clicked.connect(self.on_send_to_scratchpad)

        self.btn_export = QPushButton("Export Markdown")
        self.btn_export.clicked.connect(self.on_export)

        btn_row.addWidget(self.btn_generate)
        btn_row.addWidget(self.btn_to_scratchpad)
        btn_row.addWidget(self.btn_export)
        root.addLayout(btn_row)

        self.out = QTextEdit()
        self.out.setReadOnly(True)
        self.out.setPlaceholderText("Generated plane dossier will appear here...")
        root.addWidget(self.out, 1)

        hint = QLabel("Tip: Lock a name and re-roll tone/classification to explore variations of the same plane.")
        hint.setStyleSheet("opacity: 0.75;")
        root.addWidget(hint)

    def _refresh_seed_display(self):
        seed = getattr(self.ctx, "master_seed", None)
        self.txt_seed.setText(str(seed) if seed is not None else "(unknown)")

    # ---------------------------------------------------------------------
    # RNG + Generation
    # ---------------------------------------------------------------------
    def _derive_rng(self):
        """
        Expected: ctx.derive_rng(master_seed, plugin_id, "generate", iteration) -> random.Random
        """
        master_seed = getattr(self.ctx, "master_seed", 0) or 0
        if hasattr(self.ctx, "derive_rng"):
            return self.ctx.derive_rng(master_seed, self.PLUGIN_ID, "generate", self.generate_count)

        # Fallback deterministic RNG
        import random
        return random.Random(hash((master_seed, self.PLUGIN_ID, "generate", self.generate_count)) & 0xFFFFFFFF)

    def _collect_locks(self) -> Dict[str, Any]:
        locks: Dict[str, Any] = {}

        if self.chk_lock_name.isChecked():
            val = self.txt_locked_name.text().strip()
            locks["name"] = val or (self.last_plane.name if self.last_plane else None)
            if locks["name"] is None:
                locks.pop("name", None)

        if self.chk_lock_native.isChecked():
            val = self.txt_locked_native.text().strip()
            locks["native_name"] = val or (self.last_plane.native_name if self.last_plane else None)
            if locks["native_name"] is None:
                locks.pop("native_name", None)

        if self.chk_lock_layout.isChecked():
            val = self.txt_locked_layout.text().strip()
            locks["layout"] = val or (self.last_plane.layout if self.last_plane else None)
            if locks["layout"] is None:
                locks.pop("layout", None)

        return locks

    def on_generate(self):
        try:
            cls = self.cmb_class.currentText()
            tone = self.cmb_tone.currentText()
            depth = self.cmb_depth.currentText()

            rng = self._derive_rng()
            master_seed = getattr(self.ctx, "master_seed", 0) or 0
            locks = self._collect_locks()

            plane = generate_plane(
                rng=rng,
                seed=master_seed,
                iteration=self.generate_count,
                classification=cls,
                tone=tone,
                locks=locks,
                depth=depth,
            )
            self.last_plane = plane
            self.last_markdown = plane_to_markdown(plane)
            self.out.setPlainText(self.last_markdown)

            # If locked, populate fields with the generated values
            if self.chk_lock_name.isChecked():
                self.txt_locked_name.setText(plane.name)
            if self.chk_lock_native.isChecked():
                self.txt_locked_native.setText(plane.native_name)
            if self.chk_lock_layout.isChecked():
                self.txt_locked_layout.setText(plane.layout)

            self.ctx.log(f"[PlanarGen] Generated plane: {plane.name} (tone={tone}, class={cls}, iter={self.generate_count})")
            self.generate_count += 1

        except Exception as e:
            self.ctx.log(f"[PlanarGen] Generation failed: {e}")
            QMessageBox.critical(self, "Planar Generator Error", f"Generation failed:\n\n{e}")

    # ---------------------------------------------------------------------
    # Scratchpad + Export
    # ---------------------------------------------------------------------
    def on_send_to_scratchpad(self):
        if not self.last_markdown:
            QMessageBox.information(self, "Planar Generator", "Generate a plane first.")
            return
        try:
            plane_name = self.last_plane.name if self.last_plane else "Unknown Plane"
            tags = ["Plane", "PlanarGen", f"Plane:{plane_name}"]

            if hasattr(self.ctx, "scratchpad_add"):
                self.ctx.scratchpad_add(text=self.last_markdown, tags=tags)
                self.ctx.log(f"[PlanarGen] Sent to scratchpad: {plane_name}")
            else:
                self.ctx.log("[PlanarGen] ctx.scratchpad_add not found; cannot send to scratchpad.")
                QMessageBox.warning(self, "Planar Generator", "Scratchpad service not available in context.")
        except Exception as e:
            self.ctx.log(f"[PlanarGen] Scratchpad add failed: {e}")
            QMessageBox.critical(self, "Planar Generator Error", f"Scratchpad failed:\n\n{e}")

    def on_export(self):
        if not self.last_plane:
            QMessageBox.information(self, "Planar Generator", "Generate a plane first.")
            return
        try:
            out_path = export_plane_markdown(self.ctx, self.last_plane)
            self.ctx.log(f"[PlanarGen] Exported markdown: {out_path}")
            QMessageBox.information(self, "Planar Generator", f"Exported:\n{out_path}")
        except Exception as e:
            self.ctx.log(f"[PlanarGen] Export failed: {e}")
            QMessageBox.critical(self, "Planar Generator Error", f"Export failed:\n\n{e}")

    # ---------------------------------------------------------------------
    # State persistence
    # ---------------------------------------------------------------------
    def serialize_state(self) -> dict:
        return {
            "version": 1,
            "ui": {
                "classification": self.cmb_class.currentText(),
                "tone": self.cmb_tone.currentText(),
                "depth": self.cmb_depth.currentText(),
                "generate_count": self.generate_count,
                "lock_name": self.chk_lock_name.isChecked(),
                "lock_native": self.chk_lock_native.isChecked(),
                "lock_layout": self.chk_lock_layout.isChecked(),
                "locked_name": self.txt_locked_name.text(),
                "locked_native": self.txt_locked_native.text(),
                "locked_layout": self.txt_locked_layout.text(),
            },
            "data": {
                "last_plane": self.last_plane.to_dict() if self.last_plane else None,
                "last_markdown": self.last_markdown,
            },
        }

    def load_state(self, state: dict) -> None:
        if not state:
            return
        try:
            ver = state.get("version", 1)
            if ver != 1:
                self.ctx.log(f"[PlanarGen] Unknown state version: {ver}")
                return

            ui = state.get("ui", {})
            self.cmb_class.setCurrentText(ui.get("classification", self.cmb_class.currentText()))
            self.cmb_tone.setCurrentText(ui.get("tone", self.cmb_tone.currentText()))
            self.cmb_depth.setCurrentText(ui.get("depth", "Standard"))

            self.generate_count = int(ui.get("generate_count", 0) or 0)

            self.chk_lock_name.setChecked(bool(ui.get("lock_name", False)))
            self.chk_lock_native.setChecked(bool(ui.get("lock_native", False)))
            self.chk_lock_layout.setChecked(bool(ui.get("lock_layout", False)))

            self.txt_locked_name.setText(ui.get("locked_name", ""))
            self.txt_locked_native.setText(ui.get("locked_native", ""))
            self.txt_locked_layout.setText(ui.get("locked_layout", ""))

            data = state.get("data", {})
            self.last_markdown = data.get("last_markdown", "") or ""
            if self.last_markdown:
                self.out.setPlainText(self.last_markdown)

            self._refresh_seed_display()
            self.ctx.log(f"[PlanarGen] State loaded (generate_count={self.generate_count})")
        except Exception as e:
            self.ctx.log(f"[PlanarGen] load_state failed (ignored): {e}")
