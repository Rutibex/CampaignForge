from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional
import json

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QSlider, QSpinBox, QTextEdit, QGroupBox, QCheckBox, QLineEdit,
    QTabWidget, QMessageBox, QApplication
)

from .generator import AdventureSettings, AdventureSeed, generate_adventure_seed, load_tables, seed_to_markdown
from .exports import export_seed_session_pack


class AdventureSeedWidget(QWidget):
    PLUGIN_ID = "adventure_seed"
    STATE_VERSION = 1

    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx

        self._iteration = 0
        self._tables = None  # loaded lazily
        self._last_seed: Optional[AdventureSeed] = None

        self._build_ui()
        self._wire()

        self._refresh_outputs()

    # ---------------- UI ----------------

    def _build_ui(self):
        root = QVBoxLayout(self)

        # Controls row
        controls = QGroupBox("Adventure Seed Engine")
        c = QVBoxLayout(controls)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Tone:"))
        self.tone = QComboBox()
        self.tone.addItems(["neutral", "grim", "pulp", "weird"])
        row1.addWidget(self.tone)

        row1.addSpacing(10)
        row1.addWidget(QLabel("Scope:"))
        self.scope = QComboBox()
        self.scope.addItems(["one_session", "mini_arc"])
        row1.addWidget(self.scope)

        row1.addSpacing(10)
        row1.addWidget(QLabel("Danger:"))
        self.danger = QSlider(Qt.Horizontal)
        self.danger.setRange(0, 100)
        self.danger.setValue(50)
        self.danger_val = QSpinBox()
        self.danger_val.setRange(0, 100)
        self.danger_val.setValue(50)
        row1.addWidget(self.danger, 1)
        row1.addWidget(self.danger_val)

        c.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Title hint (optional):"))
        self.title_hint = QLineEdit()
        self.title_hint.setPlaceholderText("e.g. 'swamp cult', 'winter caravan', 'haunted abbey'…")
        row2.addWidget(self.title_hint, 1)
        c.addLayout(row2)

        # Locks + rerolls
        locks = QGroupBox("Locks / Rerolls")
        l = QHBoxLayout(locks)

        def lock_col(label: str):
            box = QGroupBox(label)
            v = QVBoxLayout(box)
            chk = QCheckBox("Lock")
            btn = QPushButton("Reroll")
            v.addWidget(chk)
            v.addWidget(btn)
            v.addStretch(1)
            return box, chk, btn

        self.lock_hook_box, self.lock_hook, self.reroll_hook = lock_col("Hook")
        self.lock_location_box, self.lock_location, self.reroll_location = lock_col("Location")
        self.lock_antagonist_box, self.lock_antagonist, self.reroll_antagonist = lock_col("Antagonist")
        self.lock_twist_box, self.lock_twist, self.reroll_twist = lock_col("Twist")
        self.lock_clock_box, self.lock_clock, self.reroll_clock = lock_col("Clock")

        for w in [self.lock_hook_box, self.lock_location_box, self.lock_antagonist_box, self.lock_twist_box, self.lock_clock_box]:
            l.addWidget(w)

        c.addWidget(locks)

        # Primary actions
        actions = QHBoxLayout()
        self.generate_btn = QPushButton("Generate Seed")
        self.generate_btn.setDefault(True)
        self.copy_btn = QPushButton("Copy Markdown")
        self.copy_btn.setEnabled(False)
        self.scratch_btn = QPushButton("Send to Scratchpad")
        self.scratch_btn.setEnabled(False)
        self.export_btn = QPushButton("Export Session Pack")
        self.export_btn.setEnabled(False)

        actions.addWidget(self.generate_btn)
        actions.addStretch(1)
        actions.addWidget(self.copy_btn)
        actions.addWidget(self.scratch_btn)
        actions.addWidget(self.export_btn)
        c.addLayout(actions)

        root.addWidget(controls)

        # Outputs tabs
        self.tabs = QTabWidget()
        self.summary = QTextEdit()
        self.summary.setReadOnly(True)
        self.tabs.addTab(self.summary, "Summary")

        self.hook_view = QTextEdit(); self.hook_view.setReadOnly(True)
        self.loc_view = QTextEdit(); self.loc_view.setReadOnly(True)
        self.ant_view = QTextEdit(); self.ant_view.setReadOnly(True)
        self.twist_view = QTextEdit(); self.twist_view.setReadOnly(True)
        self.clock_view = QTextEdit(); self.clock_view.setReadOnly(True)

        self.tabs.addTab(self.hook_view, "Hook")
        self.tabs.addTab(self.loc_view, "Location")
        self.tabs.addTab(self.ant_view, "Antagonist")
        self.tabs.addTab(self.twist_view, "Twist")
        self.tabs.addTab(self.clock_view, "Clock")

        root.addWidget(self.tabs, 1)

        # Footer hint
        self.footer = QLabel("Tip: Lock the parts you like, then reroll the rest until it clicks.")
        self.footer.setAlignment(Qt.AlignLeft)
        root.addWidget(self.footer)

    def _wire(self):
        self.generate_btn.clicked.connect(self.on_generate)
        self.copy_btn.clicked.connect(self.on_copy)
        self.scratch_btn.clicked.connect(self.on_send_scratchpad)
        self.export_btn.clicked.connect(self.on_export)

        # Keep slider and spinbox in sync
        self.danger.valueChanged.connect(self.danger_val.setValue)
        self.danger_val.valueChanged.connect(self.danger.setValue)

        # Rerolls
        self.reroll_hook.clicked.connect(lambda: self.on_reroll("hook"))
        self.reroll_location.clicked.connect(lambda: self.on_reroll("location"))
        self.reroll_antagonist.clicked.connect(lambda: self.on_reroll("antagonist"))
        self.reroll_twist.clicked.connect(lambda: self.on_reroll("twist"))
        self.reroll_clock.clicked.connect(lambda: self.on_reroll("clock"))

    # ---------------- logic ----------------

    def _tables_path(self) -> Path:
        return Path(__file__).resolve().parent / "tables" / "tables_v1.json"

    def _ensure_tables(self) -> bool:
        if self._tables is not None:
            return True
        try:
            self._tables = load_tables(self._tables_path())
            return True
        except Exception as e:
            self.ctx.log(f"[AdventureSeed] Failed to load tables: {e}")
            QMessageBox.critical(self, "Adventure Seed Engine", f"Failed to load tables.\n\n{e}")
            self._tables = {"hooks": [], "locations": [], "antagonists": [], "twists": [], "clocks": [], "fragments": {}}
            return False

    def _current_settings(self) -> AdventureSettings:
        return AdventureSettings(
            tone=str(self.tone.currentText()).strip(),
            scope=str(self.scope.currentText()).strip(),
            danger=int(self.danger.value()),
            title_hint=str(self.title_hint.text()).strip(),
        )

    def _lock_flags(self) -> Dict[str, bool]:
        return {
            "hook": bool(self.lock_hook.isChecked()),
            "location": bool(self.lock_location.isChecked()),
            "antagonist": bool(self.lock_antagonist.isChecked()),
            "twist": bool(self.lock_twist.isChecked()),
            "clock": bool(self.lock_clock.isChecked()),
        }

    def _derive_rng(self, purpose: str, iteration: int):
        # deterministic per click / reroll
        return self.ctx.derive_rng(self.ctx.master_seed, self.PLUGIN_ID, purpose, iteration, self.tone.currentText(), self.scope.currentText(), int(self.danger.value()))

    def on_generate(self):
        self._ensure_tables()
        self._iteration += 1
        settings = self._current_settings()
        rng = self._derive_rng("generate", self._iteration)
        derived_seed = self.ctx.derive_seed(self.ctx.master_seed, self.PLUGIN_ID, "generate", self._iteration, settings.tone, settings.scope, settings.danger)
        try:
            seed = generate_adventure_seed(
                rng=rng,
                master_seed=int(self.ctx.master_seed),
                derived_seed=int(derived_seed),
                iteration=int(self._iteration),
                settings=settings,
                tables=self._tables,
                lock=self._lock_flags(),
                previous=self._last_seed
            )
            self._last_seed = seed
            self._refresh_outputs()
            self.ctx.log(f"[AdventureSeed] Generated seed {seed.derived_seed} ({seed.seed_id})")
        except Exception as e:
            self.ctx.log(f"[AdventureSeed] Generate failed: {e}")
            QMessageBox.warning(self, "Adventure Seed Engine", f"Generation failed.\n\n{e}")

    def on_reroll(self, part: str):
        if not self._last_seed:
            return
        self._ensure_tables()
        # Temporarily lock everything else
        lock = self._lock_flags()
        for k in lock.keys():
            lock[k] = True
        lock[part] = False

        self._iteration += 1
        settings = self._current_settings()
        rng = self._derive_rng(f"reroll_{part}", self._iteration)
        derived_seed = self.ctx.derive_seed(self.ctx.master_seed, self.PLUGIN_ID, f"reroll_{part}", self._iteration, settings.tone, settings.scope, settings.danger)

        try:
            seed = generate_adventure_seed(
                rng=rng,
                master_seed=int(self.ctx.master_seed),
                derived_seed=int(derived_seed),
                iteration=int(self._iteration),
                settings=settings,
                tables=self._tables,
                lock=lock,
                previous=self._last_seed
            )
            self._last_seed = seed
            self._refresh_outputs()
            self.ctx.log(f"[AdventureSeed] Rerolled {part} → seed {seed.derived_seed}")
        except Exception as e:
            self.ctx.log(f"[AdventureSeed] Reroll failed: {e}")
            QMessageBox.warning(self, "Adventure Seed Engine", f"Reroll failed.\n\n{e}")

    def on_copy(self):
        if not self._last_seed:
            return
        md = seed_to_markdown(self._last_seed)
        QApplication.clipboard().setText(md)
        self.ctx.log("[AdventureSeed] Copied markdown to clipboard.")

    def on_send_scratchpad(self):
        if not self._last_seed:
            return
        md = seed_to_markdown(self._last_seed)
        tags = list(self._last_seed.tags or [])
        self.ctx.scratchpad_add(md, tags)
        self.ctx.log(f"[AdventureSeed] Sent to scratchpad (tags: {', '.join(tags)})")

    def on_export(self):
        if not self._last_seed:
            return
        try:
            pack_dir = export_seed_session_pack(self.ctx, self._last_seed)
            self.ctx.log(f"[AdventureSeed] Exported session pack: {pack_dir}")
            QMessageBox.information(self, "Adventure Seed Engine", f"Exported session pack:\n{pack_dir}")
        except Exception as e:
            self.ctx.log(f"[AdventureSeed] Export failed: {e}")
            QMessageBox.warning(self, "Adventure Seed Engine", f"Export failed.\n\n{e}")

    def _refresh_outputs(self):
        has = self._last_seed is not None
        self.copy_btn.setEnabled(has)
        self.scratch_btn.setEnabled(has)
        self.export_btn.setEnabled(has)

        if not has:
            self.summary.setPlainText("Click **Generate Seed** to create tonight's adventure.\n\nLock parts you like, then reroll the rest.")
            self.hook_view.setPlainText("")
            self.loc_view.setPlainText("")
            self.ant_view.setPlainText("")
            self.twist_view.setPlainText("")
            self.clock_view.setPlainText("")
            return

        seed = self._last_seed
        md = seed_to_markdown(seed)
        self.summary.setMarkdown(md)

        # component views: show key/value cleanly
        def kv(comp) -> str:
            lines = [f"{comp.type}"]
            lines.append("")
            for k, v in (comp.data or {}).items():
                if v is None or v == "":
                    continue
                key = k.replace("_", " ").title()
                if isinstance(v, list):
                    vv = ", ".join(str(x) for x in v)
                else:
                    vv = str(v)
                lines.append(f"{key}: {vv}")
            return "\n".join(lines).strip() + "\n"

        self.hook_view.setPlainText(kv(seed.hook))
        self.loc_view.setPlainText(kv(seed.location))
        self.ant_view.setPlainText(kv(seed.antagonist))
        self.twist_view.setPlainText(kv(seed.twist))

        # clock formatting
        clock_lines = [seed.clock.type, ""]
        stages = seed.clock.data.get("stages", []) or []
        triggers = seed.clock.data.get("advance_triggers", []) or []
        if stages:
            clock_lines.append("Stages:")
            for i, s in enumerate(stages, 1):
                clock_lines.append(f"  {i}. {s}")
            clock_lines.append("")
        if triggers:
            clock_lines.append("Advances when: " + ", ".join(str(t) for t in triggers))
        self.clock_view.setPlainText("\n".join(clock_lines).strip() + "\n")

    # ---------------- persistence ----------------

    def serialize_state(self) -> dict:
        state: Dict[str, Any] = {
            "version": self.STATE_VERSION,
            "iteration": int(self._iteration),
            "ui": {
                "tone_index": int(self.tone.currentIndex()),
                "scope_index": int(self.scope.currentIndex()),
                "danger": int(self.danger.value()),
                "title_hint": str(self.title_hint.text()),
                "locks": self._lock_flags(),
            },
            "last_seed": None,
        }
        if self._last_seed:
            try:
                state["last_seed"] = self._last_seed.to_jsonable()
            except Exception:
                state["last_seed"] = None
        return state

    def load_state(self, state: dict) -> None:
        state = state or {}
        ui = state.get("ui", {}) if isinstance(state, dict) else {}
        try:
            self.tone.setCurrentIndex(int(ui.get("tone_index", self.tone.currentIndex())))
        except Exception:
            pass
        try:
            self.scope.setCurrentIndex(int(ui.get("scope_index", self.scope.currentIndex())))
        except Exception:
            pass
        try:
            self.danger.setValue(int(ui.get("danger", self.danger.value())))
        except Exception:
            pass
        try:
            self.title_hint.setText(str(ui.get("title_hint", self.title_hint.text())))
        except Exception:
            pass

        locks = ui.get("locks", {}) if isinstance(ui, dict) else {}
        try: self.lock_hook.setChecked(bool(locks.get("hook", False)))
        except Exception: pass
        try: self.lock_location.setChecked(bool(locks.get("location", False)))
        except Exception: pass
        try: self.lock_antagonist.setChecked(bool(locks.get("antagonist", False)))
        except Exception: pass
        try: self.lock_twist.setChecked(bool(locks.get("twist", False)))
        except Exception: pass
        try: self.lock_clock.setChecked(bool(locks.get("clock", False)))
        except Exception: pass

        try:
            self._iteration = int(state.get("iteration", 0))
        except Exception:
            self._iteration = 0

        # Restore last seed (optional)
        last = state.get("last_seed", None) if isinstance(state, dict) else None
        if isinstance(last, dict):
            try:
                # reconstruct minimally
                from .generator import AdventureComponent, AdventureSettings, AdventureSeed
                settings = last.get("settings", {}) or {}
                s = AdventureSettings(**{k: settings.get(k) for k in ["tone", "scope", "danger", "title_hint"] if k in settings})
                def comp(key):
                    c = last.get(key, {}) or {}
                    return AdventureComponent(type=c.get("type",""), data=c.get("data", {}) or {})
                self._last_seed = AdventureSeed(
                    seed_id=str(last.get("seed_id","")),
                    generated_at=str(last.get("generated_at","")),
                    master_seed=int(last.get("master_seed", 0)),
                    derived_seed=int(last.get("derived_seed", 0)),
                    iteration=int(last.get("iteration", 0)),
                    settings=s,
                    hook=comp("hook"),
                    location=comp("location"),
                    antagonist=comp("antagonist"),
                    twist=comp("twist"),
                    clock=comp("clock"),
                    tags=list(last.get("tags", []) or []),
                )
            except Exception:
                self._last_seed = None

        self._refresh_outputs()
