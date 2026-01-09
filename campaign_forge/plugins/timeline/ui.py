from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
import uuid

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QListWidget, QListWidgetItem,
    QTextEdit, QLineEdit, QComboBox, QSplitter, QTabWidget, QGroupBox, QFormLayout,
    QSpinBox, QCheckBox, QMessageBox, QDialog, QDialogButtonBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QAbstractItemView, QInputDialog
)

from .exports import render_fronts_markdown, render_chronicle_markdown


FRONT_STATUSES = ["active", "dormant", "resolved", "catastrophic"]


def _now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat(sep=" ")  # local wall time


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


def _parse_tags(s: str) -> List[str]:
    # comma separated
    out: List[str] = []
    for t in (s or "").split(","):
        t = t.strip()
        if t:
            out.append(t)
    # de-dupe preserving order
    seen = set()
    dedup: List[str] = []
    for t in out:
        if t.lower() in seen:
            continue
        seen.add(t.lower())
        dedup.append(t)
    return dedup


def _join_tags(tags: List[str]) -> str:
    return ", ".join(tags or [])


@dataclass
class ClockDraft:
    name: str = ""
    description: str = ""
    segments_total: int = 6
    segments_filled: int = 0
    triggers: str = ""
    completion_effect: str = ""
    hidden: bool = False
    reversible: bool = False


class ClockDialog(QDialog):
    def __init__(self, parent: QWidget, title: str, draft: ClockDraft):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.draft = draft

        layout = QVBoxLayout(self)

        form = QFormLayout()
        self.name = QLineEdit(draft.name)
        self.desc = QTextEdit(draft.description)
        self.desc.setMinimumHeight(80)

        self.total = QSpinBox()
        self.total.setRange(2, 24)
        self.total.setValue(int(draft.segments_total or 6))

        self.filled = QSpinBox()
        self.filled.setRange(0, 24)
        self.filled.setValue(int(draft.segments_filled or 0))

        self.triggers = QLineEdit(draft.triggers)
        self.effect = QTextEdit(draft.completion_effect)
        self.effect.setMinimumHeight(60)

        self.hidden = QCheckBox("Hidden (GM-only)")
        self.hidden.setChecked(bool(draft.hidden))
        self.reversible = QCheckBox("Reversible (can remove segments)")
        self.reversible.setChecked(bool(draft.reversible))

        form.addRow("Name", self.name)
        form.addRow("Segments", self.total)
        form.addRow("Filled", self.filled)
        form.addRow("Advances when", self.triggers)
        form.addRow("On completion", self.effect)
        form.addRow("Description", self.desc)
        form.addRow("", self.hidden)
        form.addRow("", self.reversible)

        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        # keep filled <= total
        def _clamp():
            if self.filled.value() > self.total.value():
                self.filled.setValue(self.total.value())
        self.total.valueChanged.connect(_clamp)

    def get_clock_data(self) -> Dict[str, Any]:
        return {
            "name": self.name.text().strip(),
            "description": self.desc.toPlainText().strip(),
            "segments_total": int(self.total.value()),
            "segments_filled": int(self.filled.value()),
            "triggers": self.triggers.text().strip(),
            "completion_effect": self.effect.toPlainText().strip(),
            "hidden": bool(self.hidden.isChecked()),
            "reversible": bool(self.reversible.isChecked()),
        }


class TimelineWidget(QWidget):
    """Fronts & clocks module.

    State lives entirely on the widget and is persisted by MainWindow into:
      <project>/modules/timeline.json
    """

    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx

        self._state: Dict[str, Any] = {
            "version": 1,
            "session": {"count": 1},
            "settings": {
                "scratchpad_ticks": False,
                "scratchpad_completions": True,
            },
            "fronts": [],
            "chronicle": [],
        }

        self._active_front_id: Optional[str] = None
        self._active_clock_id: Optional[str] = None

        self._build_ui()
        self._refresh_all()

    # ---------------- UI ----------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)

        # Header row: session + quick actions
        header = QHBoxLayout()
        self.session_lbl = QLabel("Session: 1")
        self.btn_next_session = QPushButton("Next Session")
        self.btn_export = QPushButton("Export (Session Pack)")
        self.btn_add_note = QPushButton("Add Chronicle Note")

        header.addWidget(self.session_lbl)
        header.addStretch(1)
        header.addWidget(self.btn_add_note)
        header.addWidget(self.btn_export)
        header.addWidget(self.btn_next_session)
        root.addLayout(header)

        splitter = QSplitter(Qt.Horizontal)

        # Left: fronts list + buttons
        left = QWidget()
        left_l = QVBoxLayout(left)

        left_l.addWidget(QLabel("Fronts"))
        self.front_list = QListWidget()
        self.front_list.setSelectionMode(QAbstractItemView.SingleSelection)
        left_l.addWidget(self.front_list, stretch=1)

        front_btns = QHBoxLayout()
        self.btn_front_add = QPushButton("+ Front")
        self.btn_front_edit = QPushButton("Edit")
        self.btn_front_del = QPushButton("Delete")
        front_btns.addWidget(self.btn_front_add)
        front_btns.addWidget(self.btn_front_edit)
        front_btns.addWidget(self.btn_front_del)
        left_l.addLayout(front_btns)

        splitter.addWidget(left)

        # Right: tabs
        self.tabs = QTabWidget()

        self.tab_front = QWidget()
        self.tab_chronicle = QWidget()
        self.tab_settings = QWidget()

        self.tabs.addTab(self.tab_front, "Front")
        self.tabs.addTab(self.tab_chronicle, "Chronicle")
        self.tabs.addTab(self.tab_settings, "Settings")

        splitter.addWidget(self.tabs)
        splitter.setStretchFactor(1, 1)

        root.addWidget(splitter, stretch=1)

        # --- Front tab ---
        fl = QVBoxLayout(self.tab_front)

        self.front_title = QLabel("(no front selected)")
        self.front_title.setTextInteractionFlags(Qt.TextSelectableByMouse)
        fl.addWidget(self.front_title)

        # Front fields box (read-only view)
        self.front_desc = QTextEdit()
        self.front_desc.setReadOnly(True)
        self.front_desc.setMinimumHeight(80)

        self.front_meta = QLabel("")
        self.front_meta.setTextInteractionFlags(Qt.TextSelectableByMouse)

        fl.addWidget(self.front_meta)
        fl.addWidget(self.front_desc)

        clocks_box = QGroupBox("Clocks")
        cbl = QVBoxLayout(clocks_box)
        self.clock_table = QTableWidget(0, 5)
        self.clock_table.setHorizontalHeaderLabels(["Name", "Progress", "Segments", "Hidden", "Status"])
        self.clock_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.clock_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.clock_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.clock_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.clock_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.clock_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.clock_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.clock_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        cbl.addWidget(self.clock_table)

        clock_btns = QHBoxLayout()
        self.btn_clock_add = QPushButton("+ Clock")
        self.btn_clock_edit = QPushButton("Edit")
        self.btn_clock_del = QPushButton("Delete")
        clock_btns.addWidget(self.btn_clock_add)
        clock_btns.addWidget(self.btn_clock_edit)
        clock_btns.addWidget(self.btn_clock_del)
        clock_btns.addStretch(1)

        self.btn_tick = QPushButton("Advance +1")
        self.btn_tick2 = QPushButton("Advance +2")
        self.btn_back = QPushButton("-1")
        self.btn_complete = QPushButton("Complete")
        self.btn_reset = QPushButton("Reset")
        clock_btns.addWidget(self.btn_back)
        clock_btns.addWidget(self.btn_tick)
        clock_btns.addWidget(self.btn_tick2)
        clock_btns.addWidget(self.btn_complete)
        clock_btns.addWidget(self.btn_reset)

        cbl.addLayout(clock_btns)
        fl.addWidget(clocks_box, stretch=1)

        # --- Chronicle tab ---
        cl = QVBoxLayout(self.tab_chronicle)
        self.chron_table = QTableWidget(0, 6)
        self.chron_table.setHorizontalHeaderLabels(["When", "Kind", "Front", "Clock", "Δ", "Reason"])
        self.chron_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.chron_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.chron_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.chron_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.chron_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.chron_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Stretch)
        self.chron_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.chron_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.chron_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        cl.addWidget(self.chron_table, stretch=1)

        chron_btns = QHBoxLayout()
        self.btn_chron_del = QPushButton("Delete Entry")
        chron_btns.addStretch(1)
        chron_btns.addWidget(self.btn_chron_del)
        cl.addLayout(chron_btns)

        # --- Settings tab ---
        sl = QVBoxLayout(self.tab_settings)
        self.chk_ticks = QCheckBox("Send clock ticks to Scratchpad")
        self.chk_completions = QCheckBox("Send clock completions to Scratchpad")
        sl.addWidget(self.chk_ticks)
        sl.addWidget(self.chk_completions)
        sl.addStretch(1)

        # Wire events
        self.front_list.currentRowChanged.connect(self._on_front_selected)
        self.clock_table.itemSelectionChanged.connect(self._on_clock_selected)

        self.btn_front_add.clicked.connect(self._front_add)
        self.btn_front_edit.clicked.connect(self._front_edit)
        self.btn_front_del.clicked.connect(self._front_delete)

        self.btn_clock_add.clicked.connect(self._clock_add)
        self.btn_clock_edit.clicked.connect(self._clock_edit)
        self.btn_clock_del.clicked.connect(self._clock_delete)

        self.btn_tick.clicked.connect(lambda: self._clock_advance(1))
        self.btn_tick2.clicked.connect(lambda: self._clock_advance(2))
        self.btn_back.clicked.connect(lambda: self._clock_advance(-1))
        self.btn_complete.clicked.connect(self._clock_complete)
        self.btn_reset.clicked.connect(self._clock_reset)

        self.btn_next_session.clicked.connect(self._next_session)
        self.btn_export.clicked.connect(self._export_pack)
        self.btn_add_note.clicked.connect(self._add_chronicle_note)
        self.btn_chron_del.clicked.connect(self._delete_chronicle_entry)

        self.chk_ticks.stateChanged.connect(self._settings_changed)
        self.chk_completions.stateChanged.connect(self._settings_changed)

    # ---------------- State helpers ----------------

    def serialize_state(self) -> Dict[str, Any]:
        # Always return JSON-safe state
        return dict(self._state)

    def load_state(self, state: Dict[str, Any]) -> None:
        if not state:
            return
        try:
            ver = int(state.get("version", 1))
        except Exception:
            ver = 1
        if ver != 1:
            self.ctx.log(f"[Timeline] Unknown state version: {ver} (loading best-effort)")
        # best-effort merge with defaults
        base = self.serialize_state()
        base.update({k: state.get(k, base.get(k)) for k in base.keys()})
        # ensure required keys
        base.setdefault("session", {"count": 1})
        base.setdefault("settings", {"scratchpad_ticks": False, "scratchpad_completions": True})
        base.setdefault("fronts", [])
        base.setdefault("chronicle", [])
        self._state = base
        self._active_front_id = None
        self._active_clock_id = None
        self._refresh_all()

    def _settings_changed(self) -> None:
        self._state.setdefault("settings", {})
        self._state["settings"]["scratchpad_ticks"] = bool(self.chk_ticks.isChecked())
        self._state["settings"]["scratchpad_completions"] = bool(self.chk_completions.isChecked())

    def _refresh_all(self) -> None:
        self._refresh_session_label()
        self._refresh_settings_ui()
        self._refresh_front_list()
        self._refresh_front_view()
        self._refresh_chronicle_table()

    def _refresh_session_label(self) -> None:
        sess = (self._state.get("session") or {}).get("count", 1)
        self.session_lbl.setText(f"Session: {sess}")

    def _refresh_settings_ui(self) -> None:
        s = self._state.get("settings") or {}
        self.chk_ticks.blockSignals(True)
        self.chk_completions.blockSignals(True)
        self.chk_ticks.setChecked(bool(s.get("scratchpad_ticks", False)))
        self.chk_completions.setChecked(bool(s.get("scratchpad_completions", True)))
        self.chk_ticks.blockSignals(False)
        self.chk_completions.blockSignals(False)

    def _fronts(self) -> List[Dict[str, Any]]:
        return list(self._state.get("fronts") or [])

    def _find_front(self, front_id: str) -> Optional[Dict[str, Any]]:
        for f in self._state.get("fronts") or []:
            if f.get("id") == front_id:
                return f
        return None

    def _find_clock(self, front: Dict[str, Any], clock_id: str) -> Optional[Dict[str, Any]]:
        for c in front.get("clocks") or []:
            if c.get("id") == clock_id:
                return c
        return None

    # ---------------- UI refresh: fronts ----------------

    def _refresh_front_list(self) -> None:
        self.front_list.blockSignals(True)
        self.front_list.clear()

        fronts = self._fronts()

        # sort: status then name
        def _status_rank(s: str) -> int:
            s = (s or "").lower()
            return {"active": 0, "dormant": 1, "resolved": 2, "catastrophic": 3}.get(s, 9)

        fronts_sorted = sorted(fronts, key=lambda f: (_status_rank(f.get("status")), (f.get("name") or "").lower()))
        for f in fronts_sorted:
            name = f.get("name") or "(unnamed)"
            status = (f.get("status") or "active").lower()
            prefix = {
                "active": "● ",
                "dormant": "○ ",
                "resolved": "✓ ",
                "catastrophic": "! ",
            }.get(status, "• ")
            item = QListWidgetItem(prefix + name)
            item.setData(Qt.UserRole, f.get("id"))
            self.front_list.addItem(item)

        # restore selection if possible
        if self._active_front_id:
            for i in range(self.front_list.count()):
                it = self.front_list.item(i)
                if it.data(Qt.UserRole) == self._active_front_id:
                    self.front_list.setCurrentRow(i)
                    break
        elif self.front_list.count() > 0:
            self.front_list.setCurrentRow(0)

        self.front_list.blockSignals(False)

    def _on_front_selected(self, row: int) -> None:
        it = self.front_list.item(row) if row >= 0 else None
        self._active_front_id = it.data(Qt.UserRole) if it else None
        self._active_clock_id = None
        self._refresh_front_view()

    def _refresh_front_view(self) -> None:
        front = self._find_front(self._active_front_id) if self._active_front_id else None
        if not front:
            self.front_title.setText("(no front selected)")
            self.front_meta.setText("")
            self.front_desc.setPlainText("")
            self._refresh_clock_table(None)
            return

        name = front.get("name") or "(unnamed front)"
        status = (front.get("status") or "active").title()
        tags = _join_tags(front.get("tags") or [])
        self.front_title.setText(f"{name}")
        meta = f"Status: {status}"
        if tags:
            meta += f" | Tags: {tags}"
        self.front_meta.setText(meta)
        self.front_desc.setPlainText((front.get("description") or "").strip())
        self._refresh_clock_table(front)

    # ---------------- Clocks table ----------------

    def _refresh_clock_table(self, front: Optional[Dict[str, Any]]) -> None:
        self.clock_table.blockSignals(True)
        self.clock_table.setRowCount(0)
        self._active_clock_id = None

        if not front:
            self.clock_table.blockSignals(False)
            return

        clocks = list(front.get("clocks") or [])
        # stable sort: incomplete first then name
        def _done(c: Dict[str, Any]) -> int:
            try:
                return 1 if int(c.get("segments_filled") or 0) >= int(c.get("segments_total") or 0) else 0
            except Exception:
                return 0

        clocks_sorted = sorted(clocks, key=lambda c: (_done(c), (c.get("name") or "").lower()))

        for c in clocks_sorted:
            row = self.clock_table.rowCount()
            self.clock_table.insertRow(row)

            total = int(c.get("segments_total") or 6)
            filled = int(c.get("segments_filled") or 0)
            filled = max(0, min(filled, total))
            prog = f"{filled}/{total}"
            bar = "■" * filled + "□" * (total - filled)
            hidden = "Yes" if c.get("hidden") else "No"
            status = "Complete" if filled >= total else "In Progress"

            name_item = QTableWidgetItem(c.get("name") or "(unnamed)")
            name_item.setData(Qt.UserRole, c.get("id"))

            self.clock_table.setItem(row, 0, name_item)
            self.clock_table.setItem(row, 1, QTableWidgetItem(bar))
            self.clock_table.setItem(row, 2, QTableWidgetItem(prog))
            self.clock_table.setItem(row, 3, QTableWidgetItem(hidden))
            self.clock_table.setItem(row, 4, QTableWidgetItem(status))

        self.clock_table.blockSignals(False)

        # select first row by default
        if self.clock_table.rowCount() > 0:
            self.clock_table.selectRow(0)
            it = self.clock_table.item(0, 0)
            self._active_clock_id = it.data(Qt.UserRole) if it else None

    def _on_clock_selected(self) -> None:
        rows = self.clock_table.selectionModel().selectedRows()
        if not rows:
            self._active_clock_id = None
            return
        r = rows[0].row()
        it = self.clock_table.item(r, 0)
        self._active_clock_id = it.data(Qt.UserRole) if it else None

    # ---------------- CRUD: fronts ----------------

    def _front_add(self) -> None:
        name, ok = QInputDialog.getText(self, "New Front", "Front name:")
        if not ok:
            return
        name = (name or "").strip()
        if not name:
            QMessageBox.warning(self, "Front", "Front name cannot be empty.")
            return

        desc, _ = QInputDialog.getMultiLineText(self, "New Front", "Description (optional):")
        tags, _ = QInputDialog.getText(self, "New Front", "Tags (comma-separated, optional):")

        front = {
            "id": _new_id("front"),
            "name": name,
            "description": (desc or "").strip(),
            "status": "active",
            "tags": _parse_tags(tags),
            "clocks": [],
        }
        self._state.setdefault("fronts", []).append(front)
        self._log_event(kind="front_created", front=front, clock=None, delta=None, segments=None, reason=f"Created front: {name}")
        self._active_front_id = front["id"]
        self._refresh_front_list()
        self._refresh_front_view()

    def _front_edit(self) -> None:
        front = self._find_front(self._active_front_id) if self._active_front_id else None
        if not front:
            QMessageBox.information(self, "Front", "Select a front to edit.")
            return

        dlg = QDialog(self)
        dlg.setWindowTitle("Edit Front")
        layout = QVBoxLayout(dlg)
        form = QFormLayout()

        name = QLineEdit(front.get("name") or "")
        status = QComboBox()
        status.addItems([s.title() for s in FRONT_STATUSES])
        cur = (front.get("status") or "active").lower()
        if cur in FRONT_STATUSES:
            status.setCurrentIndex(FRONT_STATUSES.index(cur))
        tags = QLineEdit(_join_tags(front.get("tags") or []))
        desc = QTextEdit(front.get("description") or "")
        desc.setMinimumHeight(120)

        form.addRow("Name", name)
        form.addRow("Status", status)
        form.addRow("Tags", tags)
        form.addRow("Description", desc)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        layout.addWidget(buttons)

        if dlg.exec() != QDialog.Accepted:
            return

        old_name = front.get("name") or ""
        front["name"] = name.text().strip() or old_name
        front["status"] = FRONT_STATUSES[status.currentIndex()] if 0 <= status.currentIndex() < len(FRONT_STATUSES) else "active"
        front["tags"] = _parse_tags(tags.text())
        front["description"] = desc.toPlainText().strip()

        self._log_event(kind="front_updated", front=front, clock=None, delta=None, segments=None, reason=f"Updated front: {front['name']}")
        self._refresh_front_list()
        self._refresh_front_view()

    def _front_delete(self) -> None:
        front = self._find_front(self._active_front_id) if self._active_front_id else None
        if not front:
            return
        name = front.get("name") or "(unnamed)"
        if QMessageBox.question(self, "Delete Front", f"Delete front '{name}' and all its clocks?") != QMessageBox.Yes:
            return
        self._state["fronts"] = [f for f in (self._state.get("fronts") or []) if f.get("id") != front.get("id")]
        self._log_event(kind="front_deleted", front=front, clock=None, delta=None, segments=None, reason=f"Deleted front: {name}")
        self._active_front_id = None
        self._active_clock_id = None
        self._refresh_front_list()
        self._refresh_front_view()

    # ---------------- CRUD: clocks ----------------

    def _clock_add(self) -> None:
        front = self._find_front(self._active_front_id) if self._active_front_id else None
        if not front:
            QMessageBox.information(self, "Clock", "Select a front first.")
            return
        draft = ClockDraft()
        dlg = ClockDialog(self, "New Clock", draft)
        if dlg.exec() != QDialog.Accepted:
            return
        data = dlg.get_clock_data()
        if not data.get("name"):
            QMessageBox.warning(self, "Clock", "Clock name cannot be empty.")
            return
        clock = {"id": _new_id("clock"), **data}
        front.setdefault("clocks", []).append(clock)
        self._log_event(kind="clock_created", front=front, clock=clock, delta=None, segments=f"{clock['segments_filled']}/{clock['segments_total']}",
                        reason=f"Created clock: {clock['name']}")
        self._refresh_front_view()
        # select newly created clock
        self._active_clock_id = clock["id"]
        self._select_clock_in_table(clock["id"])

    def _select_clock_in_table(self, clock_id: str) -> None:
        for r in range(self.clock_table.rowCount()):
            it = self.clock_table.item(r, 0)
            if it and it.data(Qt.UserRole) == clock_id:
                self.clock_table.selectRow(r)
                self._active_clock_id = clock_id
                return

    def _clock_edit(self) -> None:
        front = self._find_front(self._active_front_id) if self._active_front_id else None
        if not front or not self._active_clock_id:
            QMessageBox.information(self, "Clock", "Select a clock to edit.")
            return
        clock = self._find_clock(front, self._active_clock_id)
        if not clock:
            return
        draft = ClockDraft(
            name=clock.get("name") or "",
            description=clock.get("description") or "",
            segments_total=int(clock.get("segments_total") or 6),
            segments_filled=int(clock.get("segments_filled") or 0),
            triggers=clock.get("triggers") or "",
            completion_effect=clock.get("completion_effect") or "",
            hidden=bool(clock.get("hidden") or False),
            reversible=bool(clock.get("reversible") or False),
        )
        dlg = ClockDialog(self, "Edit Clock", draft)
        if dlg.exec() != QDialog.Accepted:
            return
        data = dlg.get_clock_data()
        if not data.get("name"):
            QMessageBox.warning(self, "Clock", "Clock name cannot be empty.")
            return

        clock.update(data)
        # clamp
        total = int(clock.get("segments_total") or 6)
        clock["segments_filled"] = max(0, min(int(clock.get("segments_filled") or 0), total))

        self._log_event(kind="clock_updated", front=front, clock=clock, delta=None, segments=f"{clock['segments_filled']}/{clock['segments_total']}",
                        reason=f"Updated clock: {clock['name']}")
        self._refresh_front_view()
        self._select_clock_in_table(clock["id"])

    def _clock_delete(self) -> None:
        front = self._find_front(self._active_front_id) if self._active_front_id else None
        if not front or not self._active_clock_id:
            return
        clock = self._find_clock(front, self._active_clock_id)
        if not clock:
            return
        name = clock.get("name") or "(unnamed)"
        if QMessageBox.question(self, "Delete Clock", f"Delete clock '{name}'?") != QMessageBox.Yes:
            return
        front["clocks"] = [c for c in (front.get("clocks") or []) if c.get("id") != clock.get("id")]
        self._log_event(kind="clock_deleted", front=front, clock=clock, delta=None, segments=None, reason=f"Deleted clock: {name}")
        self._active_clock_id = None
        self._refresh_front_view()

    # ---------------- Advancement ----------------

    def _clock_advance(self, delta: int) -> None:
        front = self._find_front(self._active_front_id) if self._active_front_id else None
        if not front or not self._active_clock_id:
            return
        clock = self._find_clock(front, self._active_clock_id)
        if not clock:
            return

        total = int(clock.get("segments_total") or 6)
        filled_before = int(clock.get("segments_filled") or 0)

        if delta < 0 and not clock.get("reversible"):
            QMessageBox.information(self, "Clock", "This clock is not reversible.")
            return

        filled_after = max(0, min(filled_before + delta, total))
        if filled_after == filled_before:
            return

        # Reason prompt
        reason, ok = QInputDialog.getText(
            self, "Advance Clock", "Reason / trigger (optional):",
            text="" if delta > 0 else "Players reduce pressure"
        )
        if not ok:
            return

        clock["segments_filled"] = filled_after

        seg_txt = f"{filled_after}/{total}"
        self._log_event(
            kind="clock_tick",
            front=front,
            clock=clock,
            delta=delta,
            segments=seg_txt,
            reason=(reason or "").strip(),
        )

        # Scratchpad (optional)
        settings = self._state.get("settings") or {}
        if settings.get("scratchpad_ticks", False):
            self._scratchpad_clock_event(front, clock, delta=delta, completed=(filled_after >= total), reason=(reason or "").strip())

        # completion
        if filled_after >= total and filled_before < total:
            self._on_clock_completed(front, clock, reason=(reason or "").strip())

        self._refresh_front_view()
        self._select_clock_in_table(clock["id"])

    def _clock_complete(self) -> None:
        front = self._find_front(self._active_front_id) if self._active_front_id else None
        if not front or not self._active_clock_id:
            return
        clock = self._find_clock(front, self._active_clock_id)
        if not clock:
            return
        total = int(clock.get("segments_total") or 6)
        filled_before = int(clock.get("segments_filled") or 0)
        if filled_before >= total:
            return
        reason, ok = QInputDialog.getText(self, "Complete Clock", "Reason (optional):", text="Clock completes")
        if not ok:
            return
        clock["segments_filled"] = total
        self._log_event(kind="clock_tick", front=front, clock=clock, delta=(total - filled_before), segments=f"{total}/{total}", reason=(reason or "").strip())
        self._on_clock_completed(front, clock, reason=(reason or "").strip())
        self._refresh_front_view()
        self._select_clock_in_table(clock["id"])

    def _clock_reset(self) -> None:
        front = self._find_front(self._active_front_id) if self._active_front_id else None
        if not front or not self._active_clock_id:
            return
        clock = self._find_clock(front, self._active_clock_id)
        if not clock:
            return
        if QMessageBox.question(self, "Reset Clock", "Reset this clock to 0 segments?") != QMessageBox.Yes:
            return
        before = int(clock.get("segments_filled") or 0)
        clock["segments_filled"] = 0
        self._log_event(kind="clock_reset", front=front, clock=clock, delta=-before, segments=f"0/{int(clock.get('segments_total') or 6)}", reason="Reset clock")
        self._refresh_front_view()
        self._select_clock_in_table(clock["id"])

    def _on_clock_completed(self, front: Dict[str, Any], clock: Dict[str, Any], *, reason: str) -> None:
        # Log completion + optionally scratchpad
        eff = (clock.get("completion_effect") or "").strip()
        self._log_event(
            kind="clock_completed",
            front=front,
            clock=clock,
            delta=None,
            segments=f"{int(clock.get('segments_filled') or 0)}/{int(clock.get('segments_total') or 0)}",
            reason=reason,
            detail=eff,
        )

        settings = self._state.get("settings") or {}
        if settings.get("scratchpad_completions", True):
            self._scratchpad_clock_event(front, clock, delta=None, completed=True, reason=reason)

        # Notify in main log
        self.ctx.log(f"[Timeline] Clock completed: {front.get('name','(front)')} — {clock.get('name','(clock)')}")
        if eff:
            self.ctx.log(f"[Timeline] Consequence: {eff}")

    # ---------------- Chronicle ----------------

    def _log_event(
        self,
        *,
        kind: str,
        front: Optional[Dict[str, Any]],
        clock: Optional[Dict[str, Any]],
        delta: Optional[int],
        segments: Optional[str],
        reason: str,
        detail: str = "",
    ) -> None:
        sess = (self._state.get("session") or {}).get("count", 1)
        entry = {
            "id": _new_id("evt"),
            "created": _now_iso(),
            "session": sess,
            "kind": kind,
            "front_id": front.get("id") if front else None,
            "front_name": front.get("name") if front else None,
            "clock_id": clock.get("id") if clock else None,
            "clock_name": clock.get("name") if clock else None,
            "delta": delta,
            "segments": segments,
            "reason": (reason or "").strip(),
            "detail": (detail or "").strip(),
        }
        self._state.setdefault("chronicle", []).append(entry)
        self._refresh_chronicle_table()

    def _refresh_chronicle_table(self) -> None:
        log = list(self._state.get("chronicle") or [])
        # newest first
        log.sort(key=lambda e: e.get("created") or "", reverse=True)

        self.chron_table.blockSignals(True)
        self.chron_table.setRowCount(0)

        for e in log:
            r = self.chron_table.rowCount()
            self.chron_table.insertRow(r)

            when = e.get("created") or ""
            kind = (e.get("kind") or "").replace("_", " ")
            front = e.get("front_name") or ""
            clock = e.get("clock_name") or ""
            delta = ""
            if e.get("delta") is not None:
                delta = str(e.get("delta"))
            reason = e.get("reason") or ""

            it_when = QTableWidgetItem(when)
            it_when.setData(Qt.UserRole, e.get("id"))

            self.chron_table.setItem(r, 0, it_when)
            self.chron_table.setItem(r, 1, QTableWidgetItem(kind))
            self.chron_table.setItem(r, 2, QTableWidgetItem(front))
            self.chron_table.setItem(r, 3, QTableWidgetItem(clock))
            self.chron_table.setItem(r, 4, QTableWidgetItem(delta))
            self.chron_table.setItem(r, 5, QTableWidgetItem(reason))

        self.chron_table.blockSignals(False)

    def _add_chronicle_note(self) -> None:
        text, ok = QInputDialog.getMultiLineText(self, "Chronicle Note", "Add a note:")
        if not ok:
            return
        text = (text or "").strip()
        if not text:
            return
        front = self._find_front(self._active_front_id) if self._active_front_id else None
        self._log_event(kind="note", front=front, clock=None, delta=None, segments=None, reason=text)

        # also send to scratchpad as a free note
        tags = ["Chronicle"]
        if front and front.get("name"):
            tags.append(f"Front:{front['name']}")
        self.ctx.scratchpad_add(f"## Chronicle Note\n\n{text}\n", tags=tags)

    def _delete_chronicle_entry(self) -> None:
        rows = self.chron_table.selectionModel().selectedRows()
        if not rows:
            return
        r = rows[0].row()
        it = self.chron_table.item(r, 0)
        evt_id = it.data(Qt.UserRole) if it else None
        if not evt_id:
            return
        if QMessageBox.question(self, "Delete", "Delete this chronicle entry?") != QMessageBox.Yes:
            return
        self._state["chronicle"] = [e for e in (self._state.get("chronicle") or []) if e.get("id") != evt_id]
        self._refresh_chronicle_table()

    # ---------------- Scratchpad formatting ----------------

    def _scratchpad_clock_event(self, front: Dict[str, Any], clock: Dict[str, Any], *, delta: Optional[int], completed: bool, reason: str) -> None:
        front_name = front.get("name") or "(front)"
        clock_name = clock.get("name") or "(clock)"
        total = int(clock.get("segments_total") or 6)
        filled = int(clock.get("segments_filled") or 0)
        bar = "■" * max(0, min(filled, total)) + "□" * max(0, total - max(0, min(filled, total)))
        kind = "Clock Completed" if completed else "Clock Advanced" if (delta or 0) > 0 else "Clock Reduced"

        lines = []
        lines.append(f"## {kind}: {front_name} — {clock_name}")
        lines.append(f"**Progress:** `{filled}/{total}` {bar}")
        if reason:
            lines.append(f"**Reason:** {reason}")
        trig = (clock.get("triggers") or "").strip()
        if trig:
            lines.append(f"**Advances when:** {trig}")
        if completed:
            eff = (clock.get("completion_effect") or "").strip()
            if eff:
                lines.append("\n### Consequence\n" + eff)

        text = "\n\n".join(lines) + "\n"
        tags = ["Front", "Clock", f"Front:{front_name}", f"Clock:{clock_name}"]
        self.ctx.scratchpad_add(text, tags=tags)

    # ---------------- Session / Export ----------------

    def _next_session(self) -> None:
        sess = self._state.setdefault("session", {}).get("count", 1)
        try:
            sess = int(sess)
        except Exception:
            sess = 1
        sess += 1
        self._state["session"]["count"] = sess
        self._refresh_session_label()
        self._log_event(kind="session_advance", front=None, clock=None, delta=None, segments=None, reason=f"Advanced to session {sess}")
        self.ctx.log(f"[Timeline] Session advanced to {sess}")

    def _export_pack(self) -> None:
        try:
            pack = self.ctx.export_manager.create_session_pack("timeline")
            fronts_md = render_fronts_markdown(self.serialize_state())
            chron_md = render_chronicle_markdown(self.serialize_state())
            p1 = self.ctx.export_manager.write_markdown(pack, "fronts", fronts_md)
            p2 = self.ctx.export_manager.write_markdown(pack, "chronicle", chron_md)
            self.ctx.log(f"[Timeline] Exported session pack: {pack}")
            self.ctx.log(f" - {p1.name}")
            self.ctx.log(f" - {p2.name}")
            QMessageBox.information(self, "Export", f"Exported:\n{pack}")
        except Exception as e:
            self.ctx.log(f"[Timeline] Export failed: {e}")
            QMessageBox.warning(self, "Export", f"Export failed: {e}")

