from __future__ import annotations

from typing import Any, Dict, List, Optional
from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QListWidget, QListWidgetItem, QVBoxLayout, QHBoxLayout, QPushButton,
    QSplitter, QTabWidget, QLineEdit, QTextEdit, QLabel, QComboBox, QMessageBox,
    QFormLayout, QTableWidget, QTableWidgetItem, QAbstractItemView, QSpinBox
)

from campaign_forge.core.context import ForgeContext
from . import generator
from .exports import faction_to_markdown, build_gm_packet


def _qitem(text: str) -> QTableWidgetItem:
    it = QTableWidgetItem(text or "")
    it.setFlags(it.flags() | Qt.ItemIsEditable)
    return it


class FactionsWidget(QWidget):
    """
    Faction / Organization Builder

    - Manage multiple factions per project
    - Deterministic generation via ForgeContext master seed
    - Export to session packs (GM + player redacted)
    - Send summaries to scratchpad
    """
    STATE_VERSION = 1

    def __init__(self, ctx: ForgeContext):
        super().__init__()
        self.ctx = ctx
        self._data: Dict[str, Any] = {"version": self.STATE_VERSION, "selected_id": None, "factions": []}
        self._generate_count: int = 0
        self._batch_generate_count: int = 0
        self._loading_ui: bool = False

        self._build_ui()
        self._wire_signals()
        self._refresh_faction_list()

    # ---------- UI ----------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)

        splitter = QSplitter(Qt.Horizontal, self)
        root.addWidget(splitter)

        # Left pane: faction list + buttons
        left = QWidget()
        left_layout = QVBoxLayout(left)

        self.list = QListWidget()
        left_layout.addWidget(QLabel("Factions"))
        left_layout.addWidget(self.list, 1)

        btn_row = QHBoxLayout()
        self.btn_new = QPushButton("New")
        self.btn_generate = QPushButton("Generate")
        self.btn_duplicate = QPushButton("Duplicate")
        self.btn_delete = QPushButton("Delete")
        btn_row.addWidget(self.btn_new)
        btn_row.addWidget(self.btn_generate)
        btn_row.addWidget(self.btn_duplicate)
        btn_row.addWidget(self.btn_delete)

        left_layout.addLayout(btn_row)

        batch_row = QHBoxLayout()
        self.sp_batch_count = QSpinBox()
        self.sp_batch_count.setRange(2, 30)
        self.sp_batch_count.setValue(6)
        self.cb_batch_richness = QComboBox()
        self.cb_batch_richness.addItems(["Light", "Standard", "Heavy"])
        self.btn_generate_batch = QPushButton("Generate Batch")
        batch_row.addWidget(QLabel("Count"))
        batch_row.addWidget(self.sp_batch_count)
        batch_row.addWidget(self.cb_batch_richness, 1)
        left_layout.addLayout(batch_row)
        left_layout.addWidget(self.btn_generate_batch)

        splitter.addWidget(left)


        # Right pane: tabs
        right = QWidget()
        right_layout = QVBoxLayout(right)

        self.tabs = QTabWidget()
        right_layout.addWidget(self.tabs, 1)

        # Overview tab
        self.tab_overview = QWidget()
        form = QFormLayout(self.tab_overview)

        self.ed_name = QLineEdit()
        self.cb_type = QComboBox()
        self.cb_type.addItems(generator.FACTION_TYPES)

        self.ed_ethos = QLineEdit()
        self.cb_threat = QComboBox()
        self.cb_threat.addItems(["Local", "Regional", "Major", "Existential"])

        self.cb_tone = QComboBox()
        self.cb_tone.addItems(["Grim", "Political", "Weird", "Heroic", "Bleak"])

        self.ed_motto = QLineEdit()
        self.ed_public_face = QLineEdit()
        self.ed_hidden_truth = QLineEdit()

        self.ed_tags = QLineEdit()
        self.tx_notes = QTextEdit()
        self.tx_notes.setPlaceholderText("Notes (GM-facing).")

        form.addRow("Name", self.ed_name)
        form.addRow("Type", self.cb_type)
        form.addRow("Ethos", self.ed_ethos)
        form.addRow("Threat", self.cb_threat)
        form.addRow("Tone", self.cb_tone)
        form.addRow("Motto", self.ed_motto)
        form.addRow("Public Face", self.ed_public_face)
        form.addRow("Hidden Truth", self.ed_hidden_truth)
        form.addRow("Tags (comma)", self.ed_tags)
        form.addRow("Notes", self.tx_notes)

        self.tabs.addTab(self.tab_overview, "Overview")

        # Goals tab
        self.tab_goals = QWidget()
        v = QVBoxLayout(self.tab_goals)
        self.goals_table = QTableWidget(0, 7)
        self.goals_table.setHorizontalHeaderLabels(["Type", "Description", "Priority", "Visibility", "Progress %", "Deadline", "Notes"])
        self.goals_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.goals_table.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed | QAbstractItemView.SelectedClicked)
        v.addWidget(self.goals_table, 1)

        gbtns = QHBoxLayout()
        self.btn_goal_add = QPushButton("Add Goal")
        self.btn_goal_del = QPushButton("Remove Goal")
        self.btn_goal_gen = QPushButton("Generate Goal")
        gbtns.addWidget(self.btn_goal_add)
        gbtns.addWidget(self.btn_goal_gen)
        gbtns.addWidget(self.btn_goal_del)
        v.addLayout(gbtns)

        self.tabs.addTab(self.tab_goals, "Goals")

        # Assets tab
        self.tab_assets = QWidget()
        v = QVBoxLayout(self.tab_assets)
        self.assets_table = QTableWidget(0, 7)
        self.assets_table.setHorizontalHeaderLabels(["Category", "Name", "Security", "Mobility", "Known", "Tags", "Notes"])
        self.assets_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.assets_table.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed | QAbstractItemView.SelectedClicked)
        v.addWidget(self.assets_table, 1)

        abtns = QHBoxLayout()
        self.btn_asset_add = QPushButton("Add Asset")
        self.btn_asset_del = QPushButton("Remove Asset")
        self.btn_asset_gen = QPushButton("Generate Asset")
        abtns.addWidget(self.btn_asset_add)
        abtns.addWidget(self.btn_asset_gen)
        abtns.addWidget(self.btn_asset_del)
        v.addLayout(abtns)

        self.tabs.addTab(self.tab_assets, "Assets")

        # Relationships tab
        self.tab_rels = QWidget()
        v = QVBoxLayout(self.tab_rels)
        self.rels_table = QTableWidget(0, 4)
        self.rels_table.setHorizontalHeaderLabels(["Type", "Target Faction", "Tension", "History / Notes"])
        self.rels_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.rels_table.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed | QAbstractItemView.SelectedClicked)
        v.addWidget(self.rels_table, 1)

        rbtns = QHBoxLayout()
        self.btn_rel_add = QPushButton("Add Relationship")
        self.btn_rel_del = QPushButton("Remove Relationship")
        rbtns.addWidget(self.btn_rel_add)
        rbtns.addWidget(self.btn_rel_del)
        v.addLayout(rbtns)

        self.tabs.addTab(self.tab_rels, "Relationships")

        # Schisms tab
        self.tab_schisms = QWidget()
        v = QVBoxLayout(self.tab_schisms)
        self.schisms_table = QTableWidget(0, 6)
        self.schisms_table.setHorizontalHeaderLabels(["Type", "Side A (power%)", "Side B (power%)", "Clock", "Flashpoint", "Outcome/Notes"])
        self.schisms_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.schisms_table.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed | QAbstractItemView.SelectedClicked)
        v.addWidget(self.schisms_table, 1)

        sbtns = QHBoxLayout()
        self.btn_schism_add = QPushButton("Add Schism")
        self.btn_schism_del = QPushButton("Remove Schism")
        self.btn_schism_gen = QPushButton("Generate Schism")
        sbtns.addWidget(self.btn_schism_add)
        sbtns.addWidget(self.btn_schism_gen)
        sbtns.addWidget(self.btn_schism_del)
        v.addLayout(sbtns)

        self.tabs.addTab(self.tab_schisms, "Schisms")

        # Timeline tab
        self.tab_timeline = QWidget()
        v = QVBoxLayout(self.tab_timeline)
        self.timeline_table = QTableWidget(0, 4)
        self.timeline_table.setHorizontalHeaderLabels(["Created", "Title", "Details", "Tags"])
        self.timeline_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.timeline_table.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed | QAbstractItemView.SelectedClicked)
        v.addWidget(self.timeline_table, 1)

        tbtns = QHBoxLayout()
        self.btn_event_add = QPushButton("Add Event")
        self.btn_event_del = QPushButton("Remove Event")
        self.btn_event_gen = QPushButton("Generate Event")
        self.btn_advance = QPushButton("Advance Clocks")
        tbtns.addWidget(self.btn_event_add)
        tbtns.addWidget(self.btn_event_gen)
        tbtns.addWidget(self.btn_event_del)
        tbtns.addStretch(1)
        tbtns.addWidget(self.btn_advance)
        v.addLayout(tbtns)

        self.tabs.addTab(self.tab_timeline, "Timeline")

        # Export tab
        self.tab_export = QWidget()
        v = QVBoxLayout(self.tab_export)
        self.btn_export_pack = QPushButton("Export Session Pack (GM + Player)")
        self.btn_export_gm = QPushButton("Export GM Markdown Only")
        self.btn_export_player = QPushButton("Export Player Markdown Only")
        self.btn_to_scratchpad = QPushButton("Send GM Summary to Scratchpad")
        v.addWidget(QLabel("Exports"))
        v.addWidget(self.btn_export_pack)
        v.addWidget(self.btn_export_gm)
        v.addWidget(self.btn_export_player)
        v.addSpacing(12)
        v.addWidget(QLabel("Scratchpad"))
        v.addWidget(self.btn_to_scratchpad)
        v.addStretch(1)
        self.tabs.addTab(self.tab_export, "Export")

        splitter.addWidget(right)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

    def _wire_signals(self) -> None:
        self.list.currentRowChanged.connect(self._on_select_row)

        self.btn_new.clicked.connect(self._new_faction)
        self.btn_generate.clicked.connect(self._generate_faction)
        self.btn_duplicate.clicked.connect(self._duplicate_faction)
        self.btn_delete.clicked.connect(self._delete_faction)
        self.btn_generate_batch.clicked.connect(self._generate_batch)

        self.btn_goal_add.clicked.connect(self._goal_add)
        self.btn_goal_del.clicked.connect(self._goal_del)
        self.btn_goal_gen.clicked.connect(self._goal_gen)

        self.btn_asset_add.clicked.connect(self._asset_add)
        self.btn_asset_del.clicked.connect(self._asset_del)
        self.btn_asset_gen.clicked.connect(self._asset_gen)

        self.btn_rel_add.clicked.connect(self._rel_add)
        self.btn_rel_del.clicked.connect(self._rel_del)

        self.btn_schism_add.clicked.connect(self._schism_add)
        self.btn_schism_del.clicked.connect(self._schism_del)
        self.btn_schism_gen.clicked.connect(self._schism_gen)

        self.btn_event_add.clicked.connect(self._event_add)
        self.btn_event_del.clicked.connect(self._event_del)
        self.btn_event_gen.clicked.connect(self._event_gen)
        self.btn_advance.clicked.connect(self._advance_clocks)

        self.btn_export_pack.clicked.connect(self._export_pack)
        self.btn_export_gm.clicked.connect(lambda: self._export_single(include_secrets=True))
        self.btn_export_player.clicked.connect(lambda: self._export_single(include_secrets=False))
        self.btn_to_scratchpad.clicked.connect(self._send_to_scratchpad)

        # Keep overview fields in sync (only on editing finished to avoid spam)
        for w in [self.ed_name, self.ed_ethos, self.ed_motto, self.ed_public_face, self.ed_hidden_truth, self.ed_tags]:
            w.editingFinished.connect(self._sync_current_from_ui)
        for cb in [self.cb_type, self.cb_threat, self.cb_tone]:
            cb.currentIndexChanged.connect(self._sync_current_from_ui)
        self.tx_notes.textChanged.connect(self._sync_current_from_ui)

        # Tables: sync on itemChanged
        for tbl in [self.goals_table, self.assets_table, self.rels_table, self.schisms_table, self.timeline_table]:
            tbl.itemChanged.connect(self._sync_current_from_ui)

    # ---------- data helpers ----------

    def _factions(self) -> List[Dict[str, Any]]:
        return self._data.setdefault("factions", [])

    def _current_id(self) -> Optional[str]:
        return self._data.get("selected_id")

    def _get_by_id(self, fid: str) -> Optional[Dict[str, Any]]:
        for f in self._factions():
            if f.get("id") == fid:
                return f
        return None

    def _current_faction(self) -> Optional[Dict[str, Any]]:
        fid = self._current_id()
        return self._get_by_id(fid) if fid else None

    def _set_current_id(self, fid: Optional[str]) -> None:
        self._data["selected_id"] = fid

    # ---------- list + selection ----------

    def _refresh_faction_list(self) -> None:
        self._loading_ui = True
        try:
            self.list.clear()
            for f in self._factions():
                it = QListWidgetItem(f.get("name", "Unnamed"))
                it.setData(Qt.UserRole, f.get("id"))
                self.list.addItem(it)

            # Restore selection
            sel = self._current_id()
            if sel:
                for i in range(self.list.count()):
                    if self.list.item(i).data(Qt.UserRole) == sel:
                        self.list.setCurrentRow(i)
                        break
            if self.list.currentRow() < 0 and self.list.count() > 0:
                self.list.setCurrentRow(0)
            if self.list.count() == 0:
                self._set_current_id(None)
                self._clear_ui()
        finally:
            self._loading_ui = False

    def _on_select_row(self, row: int) -> None:
        if self._loading_ui:
            return
        # store current edits
        self._sync_current_from_ui()

        if row < 0 or row >= self.list.count():
            self._set_current_id(None)
            self._clear_ui()
            return

        fid = self.list.item(row).data(Qt.UserRole)
        self._set_current_id(fid)
        self._load_current_to_ui()

    # ---------- UI load/store ----------

    def _clear_ui(self) -> None:
        self._loading_ui = True
        try:
            self.ed_name.setText("")
            self.ed_ethos.setText("")
            self.ed_motto.setText("")
            self.ed_public_face.setText("")
            self.ed_hidden_truth.setText("")
            self.ed_tags.setText("")
            self.tx_notes.setPlainText("")
            self.cb_type.setCurrentIndex(0)
            self.cb_threat.setCurrentIndex(0)
            self.cb_tone.setCurrentIndex(0)

            for tbl in [self.goals_table, self.assets_table, self.rels_table, self.schisms_table, self.timeline_table]:
                tbl.setRowCount(0)
        finally:
            self._loading_ui = False

    def _load_current_to_ui(self) -> None:
        f = self._current_faction()
        if not f:
            self._clear_ui()
            return

        self._loading_ui = True
        try:
            self.ed_name.setText(f.get("name", ""))
            self.cb_type.setCurrentText(f.get("type", generator.FACTION_TYPES[0]))
            self.ed_ethos.setText(f.get("ethos", ""))
            self.cb_threat.setCurrentText(f.get("threat", "Local"))
            self.cb_tone.setCurrentText(f.get("tone", "Grim"))
            self.ed_motto.setText(f.get("motto", ""))
            self.ed_public_face.setText(f.get("public_face", ""))
            self.ed_hidden_truth.setText(f.get("hidden_truth", ""))
            self.ed_tags.setText(", ".join(f.get("tags", []) or []))
            self.tx_notes.setPlainText(f.get("notes", "") or "")

            self._load_goals_table(f.get("goals") or [])
            self._load_assets_table(f.get("assets") or [])
            self._load_rels_table(f.get("relationships") or [])
            self._load_schisms_table(f.get("schisms") or [])
            self._load_timeline_table(f.get("timeline") or [])
        finally:
            self._loading_ui = False

    def _sync_current_from_ui(self) -> None:
        if self._loading_ui:
            return
        f = self._current_faction()
        if not f:
            return

        # Overview
        f["name"] = self.ed_name.text().strip() or f.get("name") or "Unnamed"
        f["type"] = self.cb_type.currentText()
        f["ethos"] = self.ed_ethos.text().strip()
        f["threat"] = self.cb_threat.currentText()
        f["tone"] = self.cb_tone.currentText()
        f["motto"] = self.ed_motto.text().strip()
        f["public_face"] = self.ed_public_face.text().strip()
        f["hidden_truth"] = self.ed_hidden_truth.text().strip()
        tags = [t.strip() for t in self.ed_tags.text().split(",") if t.strip()]
        f["tags"] = tags
        f["notes"] = self.tx_notes.toPlainText()

        # Tables
        f["goals"] = self._read_goals_table()
        f["assets"] = self._read_assets_table()
        f["relationships"] = self._read_rels_table()
        f["schisms"] = self._read_schisms_table()
        f["timeline"] = self._read_timeline_table()

        # Update list item label if name changed
        cur_row = self.list.currentRow()
        if cur_row >= 0 and cur_row < self.list.count():
            it = self.list.item(cur_row)
            if it and it.data(Qt.UserRole) == f.get("id"):
                if it.text() != f["name"]:
                    it.setText(f["name"])

    # ---------- tables load/read ----------

    def _load_goals_table(self, goals: List[Dict[str, Any]]) -> None:
        self.goals_table.setRowCount(0)
        for g in goals:
            r = self.goals_table.rowCount()
            self.goals_table.insertRow(r)
            self.goals_table.setItem(r, 0, _qitem(str(g.get("type",""))))
            self.goals_table.setItem(r, 1, _qitem(str(g.get("description",""))))
            self.goals_table.setItem(r, 2, _qitem(str(g.get("priority",""))))
            self.goals_table.setItem(r, 3, _qitem(str(g.get("visibility",""))))
            self.goals_table.setItem(r, 4, _qitem(str(g.get("progress",0))))
            self.goals_table.setItem(r, 5, _qitem(str(g.get("deadline",""))))
            self.goals_table.setItem(r, 6, _qitem(str(g.get("notes",""))))
            # store id
            self.goals_table.item(r,0).setData(Qt.UserRole, g.get("id"))

    def _read_goals_table(self) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for r in range(self.goals_table.rowCount()):
            gid = self.goals_table.item(r,0).data(Qt.UserRole) if self.goals_table.item(r,0) else None
            def cell(c): 
                it=self.goals_table.item(r,c); 
                return (it.text() if it else "").strip()
            prog_txt = cell(4)
            try:
                prog = max(0, min(100, int(float(prog_txt or "0"))))
            except Exception:
                prog = 0
            out.append({
                "id": gid or "",
                "type": cell(0),
                "description": cell(1),
                "priority": cell(2),
                "visibility": cell(3),
                "progress": prog,
                "deadline": cell(5),
                "notes": cell(6),
            })
        return out

    def _load_assets_table(self, assets: List[Dict[str, Any]]) -> None:
        self.assets_table.setRowCount(0)
        for a in assets:
            r = self.assets_table.rowCount()
            self.assets_table.insertRow(r)
            self.assets_table.setItem(r, 0, _qitem(str(a.get("category",""))))
            self.assets_table.setItem(r, 1, _qitem(str(a.get("name",""))))
            self.assets_table.setItem(r, 2, _qitem(str(a.get("security",""))))
            self.assets_table.setItem(r, 3, _qitem(str(a.get("mobility",""))))
            self.assets_table.setItem(r, 4, _qitem(str(a.get("known",""))))
            self.assets_table.setItem(r, 5, _qitem(", ".join(a.get("tags", []) or [])))
            self.assets_table.setItem(r, 6, _qitem(str(a.get("notes",""))))
            self.assets_table.item(r,0).setData(Qt.UserRole, a.get("id"))

    def _read_assets_table(self) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for r in range(self.assets_table.rowCount()):
            aid = self.assets_table.item(r,0).data(Qt.UserRole) if self.assets_table.item(r,0) else None
            def cell(c): 
                it=self.assets_table.item(r,c); 
                return (it.text() if it else "").strip()
            tags = [t.strip() for t in cell(5).split(",") if t.strip()]
            out.append({
                "id": aid or "",
                "category": cell(0),
                "name": cell(1),
                "security": cell(2),
                "mobility": cell(3),
                "known": cell(4),
                "tags": tags,
                "notes": cell(6),
            })
        return out

    def _load_rels_table(self, rels: List[Dict[str, Any]]) -> None:
        self.rels_table.setRowCount(0)
        for r0 in rels:
            r = self.rels_table.rowCount()
            self.rels_table.insertRow(r)
            self.rels_table.setItem(r, 0, _qitem(str(r0.get("type",""))))
            self.rels_table.setItem(r, 1, _qitem(str(r0.get("target",""))))
            self.rels_table.setItem(r, 2, _qitem(str(r0.get("tension",""))))
            self.rels_table.setItem(r, 3, _qitem(str(r0.get("history",""))))
            self.rels_table.item(r,0).setData(Qt.UserRole, r0.get("id"))

    def _read_rels_table(self) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for r in range(self.rels_table.rowCount()):
            rid = self.rels_table.item(r,0).data(Qt.UserRole) if self.rels_table.item(r,0) else None
            def cell(c): 
                it=self.rels_table.item(r,c); 
                return (it.text() if it else "").strip()
            out.append({
                "id": rid or "",
                "type": cell(0),
                "target": cell(1),
                "tension": cell(2),
                "history": cell(3),
            })
        return out

    def _load_schisms_table(self, schisms: List[Dict[str, Any]]) -> None:
        self.schisms_table.setRowCount(0)
        for s in schisms:
            r = self.schisms_table.rowCount()
            self.schisms_table.insertRow(r)
            fa = (s.get("factions") or [{} , {}])
            a = fa[0] if len(fa)>0 else {}
            b = fa[1] if len(fa)>1 else {}
            self.schisms_table.setItem(r, 0, _qitem(str(s.get("type",""))))
            self.schisms_table.setItem(r, 1, _qitem(f"{a.get('name','')};{a.get('power',0)}"))
            self.schisms_table.setItem(r, 2, _qitem(f"{b.get('name','')};{b.get('power',0)}"))
            self.schisms_table.setItem(r, 3, _qitem(str(s.get("clock",""))))
            self.schisms_table.setItem(r, 4, _qitem(str(s.get("flashpoint",""))))
            self.schisms_table.setItem(r, 5, _qitem(str(s.get("outcome","") or s.get("notes",""))))
            self.schisms_table.item(r,0).setData(Qt.UserRole, s.get("id"))

    def _read_schisms_table(self) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for r in range(self.schisms_table.rowCount()):
            sid = self.schisms_table.item(r,0).data(Qt.UserRole) if self.schisms_table.item(r,0) else None
            def cell(c): 
                it=self.schisms_table.item(r,c); 
                return (it.text() if it else "").strip()
            # side parsing: "Name;Power"
            def parse_side(s: str):
                if ";" in s:
                    n,p=s.split(";",1)
                else:
                    n,p=s,"0"
                try:
                    pv=max(0,min(100,int(float(p.strip() or "0"))))
                except Exception:
                    pv=0
                return {"name": n.strip(), "power": pv, "agenda": ""}
            a = parse_side(cell(1))
            b = parse_side(cell(2))
            try:
                clk = max(0, int(float(cell(3) or "0")))
            except Exception:
                clk = 0
            out.append({
                "id": sid or "",
                "type": cell(0),
                "factions": [a,b],
                "clock": clk,
                "flashpoint": cell(4),
                "outcome": "",
                "notes": cell(5),
            })
        return out

    def _load_timeline_table(self, tl: List[Dict[str, Any]]) -> None:
        self.timeline_table.setRowCount(0)
        for ev in tl:
            r = self.timeline_table.rowCount()
            self.timeline_table.insertRow(r)
            self.timeline_table.setItem(r, 0, _qitem(str(ev.get("created",""))))
            self.timeline_table.setItem(r, 1, _qitem(str(ev.get("title",""))))
            self.timeline_table.setItem(r, 2, _qitem(str(ev.get("details",""))))
            self.timeline_table.setItem(r, 3, _qitem(", ".join(ev.get("tags",[]) or [])))
            self.timeline_table.item(r,0).setData(Qt.UserRole, ev.get("id"))

    def _read_timeline_table(self) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for r in range(self.timeline_table.rowCount()):
            eid = self.timeline_table.item(r,0).data(Qt.UserRole) if self.timeline_table.item(r,0) else None
            def cell(c): 
                it=self.timeline_table.item(r,c); 
                return (it.text() if it else "").strip()
            tags = [t.strip() for t in cell(3).split(",") if t.strip()]
            out.append({
                "id": eid or "",
                "created": cell(0),
                "title": cell(1),
                "details": cell(2),
                "tags": tags,
            })
        return out

    # ---------- actions ----------

    def _new_faction(self) -> None:
        self._sync_current_from_ui()
        fid = generator.slugify("new_faction")
        existing = [f.get("id","") for f in self._factions()]
        fid = generator.ensure_unique_id(existing, fid)
        f = {
            "id": fid,
            "name": "New Faction",
            "type": generator.FACTION_TYPES[0],
            "ethos": "",
            "threat": "Local",
            "tone": "Grim",
            "public_face": "",
            "hidden_truth": "",
            "motto": "",
            "tags": [],
            "notes": "",
            "goals": [],
            "assets": [],
            "relationships": [],
            "schisms": [],
            "timeline": [],
        }
        self._factions().append(f)
        self._set_current_id(fid)
        self._refresh_faction_list()
        self.ctx.log(f"[Factions] Created faction: {f['name']}")

    def _generate_faction(self) -> None:
        self._sync_current_from_ui()
        rng = self.ctx.derive_rng("factions", "generate_faction", self._generate_count)
        self._generate_count += 1
        f = generator.generate_faction(rng)
        existing = [x.get("id","") for x in self._factions()]
        f["id"] = generator.ensure_unique_id(existing, f.get("id","faction"))
        self._factions().append(f)
        self._set_current_id(f["id"])
        self._refresh_faction_list()
        self.ctx.log(f"[Factions] Generated faction: {f.get('name')}")

    def _generate_batch(self) -> None:
        """Generate multiple fully-populated factions and auto-wire relationships."""
        self._sync_current_from_ui()
        count = int(self.sp_batch_count.value())
        richness_label = self.cb_batch_richness.currentText()
        richness = {"Light": 1, "Standard": 2, "Heavy": 3}.get(richness_label, 2)

        rng = self.ctx.derive_rng("factions", "generate_batch", self._batch_generate_count)
        self._batch_generate_count += 1

        batch = generator.generate_factions_batch(rng, count=count, richness=richness)

        # Ensure unique IDs against existing factions
        existing_ids = [x.get("id", "") for x in self._factions()]
        for f in batch:
            f["id"] = generator.ensure_unique_id(existing_ids, f.get("id", "faction"))
            existing_ids.append(f["id"])

        # Append and select first generated
        self._factions().extend(batch)
        if batch:
            self._set_current_id(batch[0]["id"])
        self._refresh_faction_list()

        self.ctx.log(f"[Factions] Generated batch: {len(batch)} factions (richness={richness_label}).")


    def _duplicate_faction(self) -> None:
        self._sync_current_from_ui()
        cur = self._current_faction()
        if not cur:
            return
        new = {**cur}
        new["name"] = f"{cur.get('name','Faction')} (Copy)"
        desired = generator.slugify(new["name"])
        existing = [x.get("id","") for x in self._factions()]
        new["id"] = generator.ensure_unique_id(existing, desired)
        # deep-ish copy lists
        for k in ["goals","assets","relationships","schisms","timeline"]:
            new[k] = [dict(x) for x in (cur.get(k) or [])]
        self._factions().append(new)
        self._set_current_id(new["id"])
        self._refresh_faction_list()
        self.ctx.log(f"[Factions] Duplicated faction: {new.get('name')}")

    def _delete_faction(self) -> None:
        cur = self._current_faction()
        if not cur:
            return
        if QMessageBox.question(self, "Delete faction", f"Delete '{cur.get('name','Faction')}'? This cannot be undone.") != QMessageBox.Yes:
            return
        fid = cur.get("id")
        self._data["factions"] = [f for f in self._factions() if f.get("id") != fid]
        self._set_current_id(None)
        self._refresh_faction_list()
        self.ctx.log(f"[Factions] Deleted faction: {cur.get('name')}")

    # Goals
    def _goal_add(self) -> None:
        self._loading_ui = True
        try:
            r = self.goals_table.rowCount()
            self.goals_table.insertRow(r)
            for c, val in enumerate(["", "", "Medium", "Rumored", "0", "", ""]):
                self.goals_table.setItem(r, c, _qitem(val))
            self.goals_table.item(r,0).setData(Qt.UserRole, "")
        finally:
            self._loading_ui = False
        self._sync_current_from_ui()

    def _goal_del(self) -> None:
        rows = sorted({i.row() for i in self.goals_table.selectedIndexes()}, reverse=True)
        for r in rows:
            self.goals_table.removeRow(r)
        self._sync_current_from_ui()

    def _goal_gen(self) -> None:
        rng = self.ctx.derive_rng("factions", "generate_goal", self._generate_count, self._current_id() or "")
        g = generator.generate_goal(rng)
        self._generate_count += 1
        self._loading_ui = True
        try:
            r = self.goals_table.rowCount()
            self.goals_table.insertRow(r)
            self.goals_table.setItem(r, 0, _qitem(g["type"]))
            self.goals_table.setItem(r, 1, _qitem(g["description"]))
            self.goals_table.setItem(r, 2, _qitem(g["priority"]))
            self.goals_table.setItem(r, 3, _qitem(g["visibility"]))
            self.goals_table.setItem(r, 4, _qitem(str(g["progress"])))
            self.goals_table.setItem(r, 5, _qitem(g["deadline"]))
            self.goals_table.setItem(r, 6, _qitem(""))
            self.goals_table.item(r,0).setData(Qt.UserRole, g["id"])
        finally:
            self._loading_ui = False
        self._sync_current_from_ui()

    # Assets
    def _asset_add(self) -> None:
        self._loading_ui = True
        try:
            r = self.assets_table.rowCount()
            self.assets_table.insertRow(r)
            for c, val in enumerate(["", "", "Medium", "Fixed", "Known", "", ""]):
                self.assets_table.setItem(r, c, _qitem(val))
            self.assets_table.item(r,0).setData(Qt.UserRole, "")
        finally:
            self._loading_ui = False
        self._sync_current_from_ui()

    def _asset_del(self) -> None:
        rows = sorted({i.row() for i in self.assets_table.selectedIndexes()}, reverse=True)
        for r in rows:
            self.assets_table.removeRow(r)
        self._sync_current_from_ui()

    def _asset_gen(self) -> None:
        rng = self.ctx.derive_rng("factions", "generate_asset", self._generate_count, self._current_id() or "")
        a = generator.generate_asset(rng)
        self._generate_count += 1
        self._loading_ui = True
        try:
            r = self.assets_table.rowCount()
            self.assets_table.insertRow(r)
            self.assets_table.setItem(r, 0, _qitem(a["category"]))
            self.assets_table.setItem(r, 1, _qitem(a["name"]))
            self.assets_table.setItem(r, 2, _qitem(a["security"]))
            self.assets_table.setItem(r, 3, _qitem(a["mobility"]))
            self.assets_table.setItem(r, 4, _qitem(a["known"]))
            self.assets_table.setItem(r, 5, _qitem(", ".join(a["tags"])))
            self.assets_table.setItem(r, 6, _qitem(a["notes"]))
            self.assets_table.item(r,0).setData(Qt.UserRole, a["id"])
        finally:
            self._loading_ui = False
        self._sync_current_from_ui()

    # Relationships
    def _rel_add(self) -> None:
        self._loading_ui = True
        try:
            r = self.rels_table.rowCount()
            self.rels_table.insertRow(r)
            for c, val in enumerate(["Enemy", "", "3", ""]):
                self.rels_table.setItem(r, c, _qitem(val))
            self.rels_table.item(r,0).setData(Qt.UserRole, "")
        finally:
            self._loading_ui = False
        self._sync_current_from_ui()

    def _rel_del(self) -> None:
        rows = sorted({i.row() for i in self.rels_table.selectedIndexes()}, reverse=True)
        for r in rows:
            self.rels_table.removeRow(r)
        self._sync_current_from_ui()

    # Schisms
    def _schism_add(self) -> None:
        self._loading_ui = True
        try:
            r = self.schisms_table.rowCount()
            self.schisms_table.insertRow(r)
            for c, val in enumerate(["Ideological split", "Purists;50", "Reformers;50", "0", "", ""]):
                self.schisms_table.setItem(r, c, _qitem(val))
            self.schisms_table.item(r,0).setData(Qt.UserRole, "")
        finally:
            self._loading_ui = False
        self._sync_current_from_ui()

    def _schism_del(self) -> None:
        rows = sorted({i.row() for i in self.schisms_table.selectedIndexes()}, reverse=True)
        for r in rows:
            self.schisms_table.removeRow(r)
        self._sync_current_from_ui()

    def _schism_gen(self) -> None:
        rng = self.ctx.derive_rng("factions", "generate_schism", self._generate_count, self._current_id() or "")
        s = generator.generate_schism(rng)
        self._generate_count += 1
        fa = s.get("factions") or [{},{}]
        a = fa[0] if len(fa)>0 else {}
        b = fa[1] if len(fa)>1 else {}
        self._loading_ui = True
        try:
            r = self.schisms_table.rowCount()
            self.schisms_table.insertRow(r)
            self.schisms_table.setItem(r, 0, _qitem(s["type"]))
            self.schisms_table.setItem(r, 1, _qitem(f"{a.get('name','')};{a.get('power',0)}"))
            self.schisms_table.setItem(r, 2, _qitem(f"{b.get('name','')};{b.get('power',0)}"))
            self.schisms_table.setItem(r, 3, _qitem(str(s.get("clock",0))))
            self.schisms_table.setItem(r, 4, _qitem(str(s.get("flashpoint",""))))
            self.schisms_table.setItem(r, 5, _qitem(str(s.get("notes",""))))
            self.schisms_table.item(r,0).setData(Qt.UserRole, s["id"])
        finally:
            self._loading_ui = False
        self._sync_current_from_ui()

    # Timeline
    def _event_add(self) -> None:
        self._loading_ui = True
        try:
            r = self.timeline_table.rowCount()
            self.timeline_table.insertRow(r)
            for c, val in enumerate(["", "", "", "FactionEvent"]):
                self.timeline_table.setItem(r, c, _qitem(val))
            self.timeline_table.item(r,0).setData(Qt.UserRole, "")
        finally:
            self._loading_ui = False
        self._sync_current_from_ui()

    def _event_del(self) -> None:
        rows = sorted({i.row() for i in self.timeline_table.selectedIndexes()}, reverse=True)
        for r in rows:
            self.timeline_table.removeRow(r)
        self._sync_current_from_ui()

    def _event_gen(self) -> None:
        f = self._current_faction()
        if not f:
            return
        rng = self.ctx.derive_rng("factions", "generate_event", self._generate_count, f.get("id",""))
        self._generate_count += 1
        ev = generator.generate_timeline_event(rng, f.get("name","Faction"))
        self._loading_ui = True
        try:
            r = self.timeline_table.rowCount()
            self.timeline_table.insertRow(r)
            self.timeline_table.setItem(r, 0, _qitem(ev["created"]))
            self.timeline_table.setItem(r, 1, _qitem(ev["title"]))
            self.timeline_table.setItem(r, 2, _qitem(ev["details"]))
            self.timeline_table.setItem(r, 3, _qitem(", ".join(ev["tags"])))
            self.timeline_table.item(r,0).setData(Qt.UserRole, ev["id"])
        finally:
            self._loading_ui = False
        self._sync_current_from_ui()

    def _advance_clocks(self) -> None:
        """
        A simple OSR-friendly "between sessions" nudge:
        - advance each goal progress by a small random amount
        - advance schism clocks occasionally
        - add a timeline event if anything moved
        """
        f = self._current_faction()
        if not f:
            return
        rng = self.ctx.derive_rng("factions", "advance", self._generate_count, f.get("id",""))
        self._generate_count += 1

        moved = False
        for g in f.get("goals", []) or []:
            if rng.random() < 0.7:
                inc = rng.randint(1, 8)
                g["progress"] = int(max(0, min(100, int(g.get("progress",0)) + inc)))
                moved = True

        for s in f.get("schisms", []) or []:
            if rng.random() < 0.4:
                s["clock"] = int(max(0, int(s.get("clock",0)) + 1))
                moved = True

        if moved:
            ev = generator.generate_timeline_event(rng, f.get("name","Faction"))
            f.setdefault("timeline", []).insert(0, ev)
            self.ctx.log(f"[Factions] Advanced clocks for {f.get('name')}")
            self._load_current_to_ui()  # refresh tables
        else:
            self.ctx.log(f"[Factions] No notable change for {f.get('name')}")

    # ---------- export + scratchpad ----------

    def _export_pack(self) -> None:
        f = self._current_faction()
        if not f:
            return
        self._sync_current_from_ui()
        seed = self.ctx.derive_seed("factions", "export", f.get("id",""))
        pack = self.ctx.export_manager.create_session_pack(f"faction_{f.get('name','faction')}", seed=seed)
        files = build_gm_packet(f)
        for filename, content in files.items():
            self.ctx.export_manager.write_markdown(pack, filename, content)
        self.ctx.log(f"[Factions] Exported session pack: {pack}")
        QMessageBox.information(self, "Export complete", f"Exported:\n{pack}")

    def _export_single(self, *, include_secrets: bool) -> None:
        f = self._current_faction()
        if not f:
            return
        self._sync_current_from_ui()
        seed = self.ctx.derive_seed("factions", "export_single", include_secrets, f.get("id",""))
        pack = self.ctx.export_manager.create_session_pack(f"faction_{f.get('name','faction')}", seed=seed)
        md = faction_to_markdown(f, include_secrets=include_secrets)
        filename = "faction_gm.md" if include_secrets else "faction_player.md"
        self.ctx.export_manager.write_markdown(pack, filename, md)
        self.ctx.log(f"[Factions] Exported {filename}: {pack}")
        QMessageBox.information(self, "Export complete", f"Exported:\n{pack / filename}")

    def _send_to_scratchpad(self) -> None:
        f = self._current_faction()
        if not f:
            return
        self._sync_current_from_ui()
        md = faction_to_markdown(f, include_secrets=True)
        tags = ["Faction", "Factions", f"Faction:{f.get('name','Faction')}"]
        try:
            self.ctx.scratchpad_add(md, tags)
            self.ctx.log(f"[Factions] Sent '{f.get('name')}' to scratchpad.")
        except Exception as e:
            self.ctx.log(f"[Factions] Scratchpad add failed: {e}")

    # ---------- persistence ----------

    def serialize_state(self) -> Dict[str, Any]:
        # Make sure we capture any in-progress edits
        self._sync_current_from_ui()

        # sanitize minimal
        data = {
            "version": self.STATE_VERSION,
            "selected_id": self._current_id(),
            "generate_count": int(self._generate_count),
            "batch_generate_count": int(self._batch_generate_count),
            "factions": self._factions(),
        }
        return data

    def load_state(self, state: Dict[str, Any]) -> None:
        self._loading_ui = True
        try:
            st = dict(state or {})
            self._data = {
                "version": st.get("version", self.STATE_VERSION),
                "selected_id": st.get("selected_id"),
                "factions": st.get("factions", []) or [],
            }
            self._generate_count = int(st.get("generate_count", 0) or 0)
            self._batch_generate_count = int(st.get("batch_generate_count", 0) or 0)
        finally:
            self._loading_ui = False

        self._refresh_faction_list()
        self._load_current_to_ui()
