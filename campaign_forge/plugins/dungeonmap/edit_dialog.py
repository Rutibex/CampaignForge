from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QComboBox,
    QCheckBox, QTextEdit, QPushButton
)

from .generator import Room, ROOM_TAGS

FUNCTIONS = ["", "lair", "shrine", "storage", "barracks", "treasury", "workshop", "library", "prison", "guardpost", "crypt", "laboratory", "armory", "messhall", "portal", "well", "nursery", "throne"]
CONDITIONS = ["", "ruined", "flooded", "pristine", "smoky", "collapsed", "moldy", "webbed", "bloodstained", "frozen"]
OCCUPANCY = ["", "empty", "active", "abandoned", "occupied"]
CONTROL = ["", "neutral", "monster", "faction"]

class RoomEditDialog(QDialog):
    def __init__(self, room: Room, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Edit Room {room.id:02d}")
        self.room = room

        root = QVBoxLayout(self)

        # Name
        row = QHBoxLayout()
        row.addWidget(QLabel("Name:"))
        self.name = QLineEdit(room.name or "")
        row.addWidget(self.name)
        root.addLayout(row)

        # Tag (legacy)
        row = QHBoxLayout()
        row.addWidget(QLabel("Tag:"))
        self.tag = QComboBox()
        self.tag.addItems(ROOM_TAGS)
        self.tag.setCurrentText(room.tag if room.tag in ROOM_TAGS else "empty")
        row.addWidget(self.tag)
        root.addLayout(row)

        # Semantics
        row = QHBoxLayout()
        row.addWidget(QLabel("Function:"))
        self.function = QComboBox(); self.function.addItems(FUNCTIONS)
        self.function.setCurrentText(room.function or "")
        row.addWidget(self.function)
        row.addWidget(QLabel("Condition:"))
        self.condition = QComboBox(); self.condition.addItems(CONDITIONS)
        self.condition.setCurrentText(room.condition or "")
        row.addWidget(self.condition)
        root.addLayout(row)

        row = QHBoxLayout()
        row.addWidget(QLabel("Occupancy:"))
        self.occupancy = QComboBox(); self.occupancy.addItems(OCCUPANCY)
        self.occupancy.setCurrentText(room.occupancy or "")
        row.addWidget(self.occupancy)
        row.addWidget(QLabel("Control:"))
        self.control = QLineEdit(room.control or "")
        self.control.setPlaceholderText("faction / monster / neutral")
        row.addWidget(self.control)
        root.addLayout(row)

        # Locks
        row = QHBoxLayout()
        self.locked = QCheckBox("Locked")
        self.locked.setChecked(bool(room.locked))
        row.addWidget(self.locked)
        row.addWidget(QLabel("Lock type:"))
        self.lock_type = QLineEdit(room.lock_type or "")
        row.addWidget(self.lock_type)
        root.addLayout(row)

        # Description + GM notes
        root.addWidget(QLabel("Description:"))
        self.description = QTextEdit()
        self.description.setPlainText(room.description or "")
        self.description.setMinimumHeight(70)
        root.addWidget(self.description)

        root.addWidget(QLabel("GM Notes:"))
        self.gm_notes = QTextEdit()
        self.gm_notes.setPlainText(room.gm_notes or "")
        self.gm_notes.setMinimumHeight(70)
        root.addWidget(self.gm_notes)

        # Contents
        root.addWidget(QLabel("Encounter:"))
        self.encounter = QTextEdit()
        self.encounter.setPlainText(room.contents.encounter or "")
        self.encounter.setMinimumHeight(60)
        root.addWidget(self.encounter)

        root.addWidget(QLabel("Trap:"))
        self.trap = QTextEdit()
        self.trap.setPlainText(room.contents.trap or "")
        self.trap.setMinimumHeight(60)
        root.addWidget(self.trap)

        root.addWidget(QLabel("Treasure:"))
        self.treasure = QTextEdit()
        self.treasure.setPlainText(room.contents.treasure or "")
        self.treasure.setMinimumHeight(60)
        root.addWidget(self.treasure)

        root.addWidget(QLabel("Notes:"))
        self.notes = QTextEdit()
        self.notes.setPlainText(room.contents.notes or "")
        self.notes.setMinimumHeight(60)
        root.addWidget(self.notes)

        # Scratchpad links
        row = QHBoxLayout()
        row.addWidget(QLabel("Linked scratchpad IDs (comma):"))
        self.links = QLineEdit(",".join(getattr(room, "linked_scratchpad_ids", []) or []))
        row.addWidget(self.links)
        root.addLayout(row)

        # Buttons
        btns = QHBoxLayout()
        btns.addStretch(1)
        self.ok = QPushButton("OK")
        self.cancel = QPushButton("Cancel")
        btns.addWidget(self.ok)
        btns.addWidget(self.cancel)
        root.addLayout(btns)

        self.ok.clicked.connect(self.accept)
        self.cancel.clicked.connect(self.reject)

    def apply_to_room(self) -> None:
        self.room.name = self.name.text().strip()
        self.room.tag = self.tag.currentText()

        self.room.function = self.function.currentText().strip()
        self.room.condition = self.condition.currentText().strip()
        self.room.occupancy = self.occupancy.currentText().strip()
        self.room.control = self.control.text().strip()

        self.room.locked = self.locked.isChecked()
        self.room.lock_type = self.lock_type.text().strip()

        self.room.description = self.description.toPlainText().strip()
        self.room.gm_notes = self.gm_notes.toPlainText().strip()

        self.room.contents.encounter = self.encounter.toPlainText().strip()
        self.room.contents.trap = self.trap.toPlainText().strip()
        self.room.contents.treasure = self.treasure.toPlainText().strip()
        self.room.contents.notes = self.notes.toPlainText().strip()

        raw = self.links.text().strip()
        if raw:
            self.room.linked_scratchpad_ids = [s.strip() for s in raw.split(",") if s.strip()]
        else:
            self.room.linked_scratchpad_ids = []
