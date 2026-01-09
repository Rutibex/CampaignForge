from __future__ import annotations
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSpinBox, QComboBox, QCheckBox, QTextEdit, QGroupBox, QApplication
)
from PySide6.QtCore import Qt

from .generator import NameGenConfig, generate_names


class NamesWidget(QWidget):
    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx

        # Controls
        self.style = QComboBox()
        self.style.addItems(["Fantasy", "Elven", "Dwarven", "Guttural"])

        self.count = QSpinBox()
        self.count.setRange(1, 1000)
        self.count.setValue(50)

        self.min_syl = QSpinBox()
        self.min_syl.setRange(1, 8)
        self.min_syl.setValue(2)

        self.max_syl = QSpinBox()
        self.max_syl.setRange(1, 10)
        self.max_syl.setValue(4)

        self.apostrophes = QCheckBox("Allow apostrophes")
        self.capitalize = QCheckBox("Capitalize")
        self.capitalize.setChecked(True)

        self.generate_btn = QPushButton("Generate")
        self.copy_btn = QPushButton("Copy")
        self.copy_btn.setEnabled(False)


        self.send_btn = QPushButton("Send to Scratchpad")
        self.send_btn.setEnabled(False)

        self.output = QTextEdit()
        self.output.setPlaceholderText("Generated names will appear here...")
        self.output.setLineWrapMode(QTextEdit.NoWrap)

        # Layout
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)

        controls_box = QGroupBox("Settings")
        controls = QVBoxLayout(controls_box)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Style:"))
        row1.addWidget(self.style, stretch=1)
        row1.addWidget(QLabel("Count:"))
        row1.addWidget(self.count)
        controls.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Syllables min:"))
        row2.addWidget(self.min_syl)
        row2.addWidget(QLabel("max:"))
        row2.addWidget(self.max_syl)
        row2.addStretch(1)
        controls.addLayout(row2)

        row3 = QHBoxLayout()
        row3.addWidget(self.apostrophes)
        row3.addWidget(self.capitalize)
        row3.addStretch(1)
        row3.addWidget(self.generate_btn)
        row3.addWidget(self.copy_btn)
        row3.addWidget(self.send_btn)
        controls.addLayout(row3)

        root.addWidget(controls_box)
        root.addWidget(self.output, stretch=1)

        # Signals
        self.generate_btn.clicked.connect(self.on_generate)
        self.copy_btn.clicked.connect(self.on_copy)
        self.send_btn.clicked.connect(self.on_send)

    def on_generate(self):
        # Clamp logic
        min_s = self.min_syl.value()
        max_s = self.max_syl.value()
        if max_s < min_s:
            max_s = min_s
            self.max_syl.setValue(max_s)

        cfg = NameGenConfig(
            style=self.style.currentText(),
            count=self.count.value(),
            min_syllables=min_s,
            max_syllables=max_s,
            allow_apostrophes=self.apostrophes.isChecked(),
            capitalize=self.capitalize.isChecked(),
            seed=None,  # Later: optionally tie to project seed
        )

        names = generate_names(cfg, rng=self.ctx.rng)
        text = "\n".join(names)
        self.output.setPlainText(text)
        self.copy_btn.setEnabled(True)
        self.send_btn.setEnabled(True)
        self.ctx.log(f"[Names] Generated {len(names)} names (style={cfg.style}, syllables={cfg.min_syllables}-{cfg.max_syllables}).")

    def on_copy(self):
        text = self.output.toPlainText().strip()
        if not text:
            return
        QApplication.clipboard().setText(text)
        self.ctx.log("[Names] Copied output to clipboard.")


    def on_send(self):
        text = self.output.toPlainText().strip()
        if not text:
            return
        self.ctx.scratchpad_add(text, tags=["NPC", "Names"])
        self.ctx.log("[Names] Sent output to scratchpad.")

    def serialize_state(self) -> dict:
        return {
            "count": int(self.count.value()),
            "min_syl": int(self.min_syl.value()),
            "max_syl": int(self.max_syl.value()),
            "style_index": int(self.style.currentIndex()),
            "apostrophes": bool(self.apostrophes.isChecked()),
            "capitalize": bool(self.capitalize.isChecked()),
        }

    def load_state(self, state: dict) -> None:
        state = state or {}
        try: self.count.setValue(int(state.get("count", self.count.value())))
        except Exception: pass
        try: self.min_syl.setValue(int(state.get("min_syl", self.min_syl.value())))
        except Exception: pass
        try: self.max_syl.setValue(int(state.get("max_syl", self.max_syl.value())))
        except Exception: pass
        try: self.style.setCurrentIndex(int(state.get("style_index", self.style.currentIndex())))
        except Exception: pass
        try: self.apostrophes.setChecked(bool(state.get("apostrophes", self.apostrophes.isChecked())))
        except Exception: pass
        try: self.capitalize.setChecked(bool(state.get("capitalize", self.capitalize.isChecked())))
        except Exception: pass
