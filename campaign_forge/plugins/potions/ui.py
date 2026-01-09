# campaign_forge/plugins/potions/ui.py

from __future__ import annotations

from typing import Any, Dict, List, Optional

# --- Qt compatibility: prefer PySide6, fallback to PyQt5 ---
try:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
        QSlider, QSpinBox, QTextEdit, QGroupBox, QCheckBox, QScrollArea,
        QLineEdit, QMessageBox, QListWidget, QListWidgetItem, QApplication
    )
    USING_PYSIDE = True
except ModuleNotFoundError:
    from PyQt5.QtCore import Qt
    from PyQt5.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
        QSlider, QSpinBox, QTextEdit, QGroupBox, QCheckBox, QScrollArea,
        QLineEdit, QMessageBox, QListWidget, QListWidgetItem, QApplication
    )
    USING_PYSIDE = False

from .generator import (
    RARITIES,
    generate_potion,
    Potion,
    potion_to_json,
)
from .exports import export_potion_session_pack



class PotionGeneratorWidget(QWidget):
    """
    Features:
      - Single generation with per-slot lock + reroll
      - Batch generation (d6/d20/custom)
      - Scratchpad send (player-facing + full rules)
      - Session-pack export (MD + JSON)
      - Favorites list (persisted)
      - Reproducible RNG via ctx.derive_rng(master_seed, plugin_id, "generate", iteration)
    """

    STATE_VERSION = 1

    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx
        self.plugin_id = "potions"

        self.generate_iteration = 0
        self.current_potion: Optional[Potion] = None

        # Slot locks: key -> dict slot data
        self.lock_enabled: Dict[str, bool] = {}
        self.locked_slot_data: Dict[str, Dict[str, Any]] = {}

        # Favorites: list of Potion JSONable dicts (keep simple)
        self.favorites: List[Dict[str, Any]] = []

        self._build_ui()

    # ---------------- UI ----------------

    def _build_ui(self):
        root = QVBoxLayout(self)

        # Controls row
        controls = QHBoxLayout()

        controls.addWidget(QLabel("Rarity:"))
        self.rarity_combo = QComboBox()
        self.rarity_combo.addItems(RARITIES)
        self.rarity_combo.setCurrentText("Uncommon")
        controls.addWidget(self.rarity_combo)

        controls.addWidget(QLabel("Absurdity:"))
        self.abs_slider = QSlider(Qt.Horizontal)
        self.abs_slider.setMinimum(0)
        self.abs_slider.setMaximum(100)
        self.abs_slider.setValue(65)
        self.abs_slider.setFixedWidth(220)
        controls.addWidget(self.abs_slider)

        self.abs_label = QLabel("65")
        self.abs_label.setFixedWidth(28)
        controls.addWidget(self.abs_label)
        self.abs_slider.valueChanged.connect(lambda v: self.abs_label.setText(str(v)))

        controls.addWidget(QLabel("Batch:"))
        self.batch_spin = QSpinBox()
        self.batch_spin.setRange(1, 200)
        self.batch_spin.setValue(1)
        controls.addWidget(self.batch_spin)

        self.slug_edit = QLineEdit()
        self.slug_edit.setPlaceholderText("export slug (optional, e.g. 'tavern_loot')")
        self.slug_edit.setFixedWidth(220)
        controls.addWidget(self.slug_edit)

        self.btn_generate = QPushButton("Generate")
        self.btn_generate.clicked.connect(self.on_generate)
        controls.addWidget(self.btn_generate)

        self.btn_generate_batch = QPushButton("Generate Batch")
        self.btn_generate_batch.clicked.connect(self.on_generate_batch)
        controls.addWidget(self.btn_generate_batch)

        root.addLayout(controls)

        # Middle: slots + text panes
        mid = QHBoxLayout()

        # Left: slot locks panel
        slot_group = QGroupBox("Ad-Lib Slots (Lock + Reroll)")
        slot_v = QVBoxLayout(slot_group)

        self.slot_list_area = QScrollArea()
        self.slot_list_area.setWidgetResizable(True)
        slot_v.addWidget(self.slot_list_area)

        self.slot_list_widget = QWidget()
        self.slot_list_layout = QVBoxLayout(self.slot_list_widget)
        self.slot_list_layout.setAlignment(Qt.AlignTop)
        self.slot_list_area.setWidget(self.slot_list_widget)

        # Buttons for locks
        lock_btns = QHBoxLayout()
        self.btn_lock_all = QPushButton("Lock All")
        self.btn_unlock_all = QPushButton("Unlock All")
        self.btn_lock_all.clicked.connect(lambda: self._set_all_locks(True))
        self.btn_unlock_all.clicked.connect(lambda: self._set_all_locks(False))
        lock_btns.addWidget(self.btn_lock_all)
        lock_btns.addWidget(self.btn_unlock_all)
        slot_v.addLayout(lock_btns)

        mid.addWidget(slot_group, 1)

        # Right: output tabs (simple: rules + player + GM)
        out_group = QGroupBox("Potion Output")
        out_v = QVBoxLayout(out_group)

        self.rules_view = QTextEdit()
        self.rules_view.setReadOnly(True)
        self.rules_view.setPlaceholderText("Generated potion rules (Markdown-ish).")
        out_v.addWidget(QLabel("Rules (MD):"))
        out_v.addWidget(self.rules_view, 3)

        self.player_view = QTextEdit()
        self.player_view.setReadOnly(True)
        out_v.addWidget(QLabel("Player-facing blurb:"))
        out_v.addWidget(self.player_view, 1)

        self.gm_view = QTextEdit()
        self.gm_view.setReadOnly(True)
        out_v.addWidget(QLabel("GM notes:"))
        out_v.addWidget(self.gm_view, 1)

        # Actions row
        actions = QHBoxLayout()

        self.btn_to_scratchpad = QPushButton("Send to Scratchpad")
        self.btn_to_scratchpad.clicked.connect(self.on_send_to_scratchpad)
        actions.addWidget(self.btn_to_scratchpad)

        self.btn_favorite = QPushButton("★ Favorite")
        self.btn_favorite.clicked.connect(self.on_favorite)
        actions.addWidget(self.btn_favorite)

        self.btn_export = QPushButton("Export Session Pack")
        self.btn_export.clicked.connect(self.on_export)
        actions.addWidget(self.btn_export)

        self.btn_copy_json = QPushButton("Copy JSON")
        self.btn_copy_json.clicked.connect(self.on_copy_json)
        actions.addWidget(self.btn_copy_json)

        out_v.addLayout(actions)

        mid.addWidget(out_group, 2)

        root.addLayout(mid)

        # Bottom: favorites
        fav_group = QGroupBox("Favorites")
        fav_v = QVBoxLayout(fav_group)
        self.fav_list = QListWidget()
        self.fav_list.itemClicked.connect(self.on_favorite_selected)
        fav_v.addWidget(self.fav_list)

        fav_btns = QHBoxLayout()
        self.btn_fav_remove = QPushButton("Remove Selected")
        self.btn_fav_remove.clicked.connect(self.on_remove_favorite)
        fav_btns.addWidget(self.btn_fav_remove)

        self.btn_fav_send = QPushButton("Send Favorite to Scratchpad")
        self.btn_fav_send.clicked.connect(self.on_send_favorite_to_scratchpad)
        fav_btns.addWidget(self.btn_fav_send)

        fav_v.addLayout(fav_btns)
        root.addWidget(fav_group)

        # Initial render
        self._render_slots({})
        self._render_favorites()

    # ---------------- Generation ----------------

    def _derive_rng(self, iteration: int):
        # Preferred pattern from your design doc
        return self.ctx.derive_rng(self.ctx.master_seed, self.plugin_id, "generate", iteration)

    def _collect_locks_for_generation(self) -> Dict[str, Dict[str, Any]]:
        """
        Build locks payload for generator: slot -> slot dict
        Only include locked slots.
        """
        locks: Dict[str, Dict[str, Any]] = {}
        for k, enabled in self.lock_enabled.items():
            if enabled and k in self.locked_slot_data:
                locks[k] = self.locked_slot_data[k]
        return locks

    def on_generate(self):
        self.generate_iteration += 1
        rng = self._derive_rng(self.generate_iteration)

        rarity = self.rarity_combo.currentText()
        absurdity = int(self.abs_slider.value())

        locks = self._collect_locks_for_generation()

        p = generate_potion(
            rng,
            rarity=rarity,
            absurdity=absurdity,
            seed=self.ctx.master_seed,
            iteration=self.generate_iteration,
            locks=locks,
        )
        self.current_potion = p

        # Update locked data with latest slot results (so "lock then generate" keeps them)
        self._sync_locked_data_from_potion(p)

        self._display_potion(p)
        self._render_slots(p.slots)

        self.ctx.log(f"[Potions] Generated: {p.name} (rarity={rarity}, absurdity={absurdity}, iter={self.generate_iteration})")

    def on_generate_batch(self):
        count = int(self.batch_spin.value())
        if count <= 0:
            return

        rarity = self.rarity_combo.currentText()
        absurdity = int(self.abs_slider.value())

        potions: List[Potion] = []
        # Batch uses iteration offsets for reproducibility
        for _ in range(count):
            self.generate_iteration += 1
            rng = self._derive_rng(self.generate_iteration)
            p = generate_potion(
                rng,
                rarity=rarity,
                absurdity=absurdity,
                seed=self.ctx.master_seed,
                iteration=self.generate_iteration,
                locks={},  # batch ignores locks by default (keeps it varied)
            )
            potions.append(p)

        # Show last
        self.current_potion = potions[-1]
        self._display_potion(potions[-1])
        self._render_slots(potions[-1].slots)

        # Send a nice bundle to scratchpad
        md = "# Potion Batch\n\n"
        md += f"- Count: **{len(potions)}**\n"
        md += f"- Rarity: **{rarity}**\n"
        md += f"- Absurdity: **{absurdity}**\n"
        md += f"- Master Seed: `{self.ctx.master_seed}`\n\n"
        md += "---\n\n"
        for p in potions:
            md += p.rules_text_md + "\n\n---\n\n"

        self.ctx.scratchpad_add(md, tags=["Item", "Potion", "Batch", "Consumable"])
        self.ctx.log(f"[Potions] Generated batch of {len(potions)} and sent to scratchpad.")

    # ---------------- Slot locking UI ----------------

    def _set_all_locks(self, enabled: bool):
        # Toggle all checkboxes in slot widgets
        for i in range(self.slot_list_layout.count()):
            w = self.slot_list_layout.itemAt(i).widget()
            if w and hasattr(w, "lock_cb"):
                w.lock_cb.setChecked(enabled)

    def _render_slots(self, slots: Dict[str, Dict[str, Any]]):
        # Clear
        while self.slot_list_layout.count():
            item = self.slot_list_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        # Define which slots are lockable/rerollable
        # (We exclude rarity/absurdity since those are controlled above.)
        order = [
            "name",
            "theme",
            "delivery",
            "container",
            "sensory",
            "trigger",
            "target",
            "duration",
            "primary",
            "side_effects",
        ]

        for key in order:
            slot = slots.get(key, {"key": key, "label": key, "value": ""})
            row = _SlotRow(
                parent=self,
                label=slot.get("label", key),
                key=key,
                value=self._slot_value_preview(slot),
                on_lock_changed=self._on_lock_changed,
                on_reroll_clicked=self._on_reroll_slot,
            )
            # init lock state
            row.lock_cb.setChecked(bool(self.lock_enabled.get(key, False)))

            self.slot_list_layout.addWidget(row)

        self.slot_list_layout.addStretch(1)

    def _slot_value_preview(self, slot: Dict[str, Any]) -> str:
        key = slot.get("key", "")
        if key == "primary":
            return slot.get("rules", "")[:140].strip().replace("\n", " ") + ("…" if len(slot.get("rules", "")) > 140 else "")
        if key == "side_effects":
            items = slot.get("items", [])
            if not items:
                return "(none)"
            # show first 2
            txts = [it.get("text", "") for it in items[:2]]
            s = " | ".join(t[:60].replace("\n", " ") for t in txts)
            if len(items) > 2:
                s += f" (+{len(items)-2} more)"
            return s
        return str(slot.get("value", ""))

    def _on_lock_changed(self, key: str, enabled: bool):
        self.lock_enabled[key] = enabled
        if enabled:
            # lock current value if possible
            if self.current_potion and key in self.current_potion.slots:
                self.locked_slot_data[key] = self.current_potion.slots[key]
        else:
            # unlocking does not delete data; harmless
            pass

    def _sync_locked_data_from_potion(self, p: Potion):
        # If slot is currently locked, update stored slot dict to p's value
        for key, enabled in self.lock_enabled.items():
            if enabled and key in p.slots:
                self.locked_slot_data[key] = p.slots[key]

    def _on_reroll_slot(self, key: str):
        """
        Reroll ONLY this slot, keeping all other slots locked as-is.
        Achieved by:
          - Lock everything except the slot
          - Generate
          - Restore previous lock states
        """
        prev_locks = dict(self.lock_enabled)

        # Ensure we have something to reroll against
        if not self.current_potion:
            self.on_generate()
            return

        # Temporarily lock all other slots
        for k in list(self.lock_enabled.keys()):
            self.lock_enabled[k] = (k != key)

        # Ensure locked_slot_data contains current values for the locked slots
        self._sync_locked_data_from_potion(self.current_potion)

        # Generate new potion
        self.on_generate()

        # Restore lock states
        self.lock_enabled = prev_locks
        # Re-render to reflect lock checkbox states
        if self.current_potion:
            self._render_slots(self.current_potion.slots)

    # ---------------- Display ----------------

    def _display_potion(self, p: Potion):
        self.rules_view.setPlainText(p.rules_text_md)
        self.player_view.setPlainText(p.player_text)
        self.gm_view.setPlainText(p.gm_notes)

    # ---------------- Scratchpad / Exports ----------------

    def on_send_to_scratchpad(self):
        if not self.current_potion:
            self.on_generate()
            if not self.current_potion:
                return

        p = self.current_potion
        md = p.rules_text_md + "\n\n---\n\n" + "### GM Notes\n" + p.gm_notes + "\n"
        tags = ["Item", "Potion", "Consumable", f"Rarity:{p.rarity}", f"Theme:{p.slots['theme']['value']}"]
        if p.absurdity >= 75:
            tags.append("Absurd")

        self.ctx.scratchpad_add(md, tags=tags)
        self.ctx.log(f"[Potions] Sent to scratchpad: {p.name}")

    def on_export(self):
        # Export current potion or batch = favorites? We'll export current potion unless none.
        if not self.current_potion:
            QMessageBox.information(self, "Export", "Generate a potion first.")
            return
        slug = self.slug_edit.text().strip()
        seed = self.ctx.master_seed

        # Export a pack containing: current potion + any selected favorites? Keep simple: current only.
        pack_dir = export_potion_session_pack(self.ctx, [self.current_potion], slug=slug, seed=seed)
        self.ctx.log(f"[Potions] Exported session pack: {pack_dir}")

    def on_copy_json(self):
        if not self.current_potion:
            return
        j = potion_to_json(self.current_potion)
        QApplication.clipboard().setText(j)
        self.ctx.log("[Potions] Copied potion JSON to clipboard.")


    # ---------------- Favorites ----------------

    def on_favorite(self):
        if not self.current_potion:
            return
        p = self.current_potion.to_jsonable()
        self.favorites.append(p)
        self._render_favorites()
        self.ctx.log(f"[Potions] Favorited: {self.current_potion.name}")

    def _render_favorites(self):
        self.fav_list.clear()
        for idx, p in enumerate(self.favorites):
            name = p.get("name", f"Potion {idx+1}")
            rarity = p.get("rarity", "?")
            absurd = p.get("absurdity", "?")
            item = QListWidgetItem(f"{name}  [{rarity}, absurd {absurd}]")
            item.setData(Qt.UserRole, idx)
            self.fav_list.addItem(item)

    def on_favorite_selected(self, item: QListWidgetItem):
        idx = item.data(Qt.UserRole)
        if idx is None:
            return
        try:
            pdata = self.favorites[int(idx)]
        except Exception:
            return
        # Display from stored dict (light reconstruction)
        rules = pdata.get("rules_text_md", "")
        player = pdata.get("player_text", "")
        gm = pdata.get("gm_notes", "")
        self.rules_view.setPlainText(rules)
        self.player_view.setPlainText(player)
        self.gm_view.setPlainText(gm)

    def on_remove_favorite(self):
        item = self.fav_list.currentItem()
        if not item:
            return
        idx = item.data(Qt.UserRole)
        if idx is None:
            return
        idx = int(idx)
        if 0 <= idx < len(self.favorites):
            removed = self.favorites.pop(idx)
            self._render_favorites()
            self.ctx.log(f"[Potions] Removed favorite: {removed.get('name','(unknown)')}")

    def on_send_favorite_to_scratchpad(self):
        item = self.fav_list.currentItem()
        if not item:
            return
        idx = int(item.data(Qt.UserRole))
        if idx < 0 or idx >= len(self.favorites):
            return
        p = self.favorites[idx]
        md = p.get("rules_text_md", "")
        gm = p.get("gm_notes", "")
        if gm:
            md += "\n\n---\n\n### GM Notes\n" + gm + "\n"
        tags = ["Item", "Potion", "Consumable", "Favorite"]
        rarity = p.get("rarity")
        if rarity:
            tags.append(f"Rarity:{rarity}")
        self.ctx.scratchpad_add(md, tags=tags)
        self.ctx.log(f"[Potions] Sent favorite to scratchpad: {p.get('name','(unknown)')}")

    # ---------------- Persistence ----------------

    def serialize_state(self) -> dict:
        return {
            "version": self.STATE_VERSION,
            "ui": {
                "rarity": self.rarity_combo.currentText(),
                "absurdity": int(self.abs_slider.value()),
                "batch": int(self.batch_spin.value()),
                "slug": self.slug_edit.text(),
            },
            "data": {
                "generate_iteration": int(self.generate_iteration),
                "lock_enabled": dict(self.lock_enabled),
                "locked_slot_data": self.locked_slot_data,
                "current_potion": self.current_potion.to_jsonable() if self.current_potion else None,
                "favorites": self.favorites,
            },
        }

    def load_state(self, state: dict) -> None:
        if not state:
            return
        ver = state.get("version", 1)
        if ver != self.STATE_VERSION:
            # Best effort: still try
            self.ctx.log(f"[Potions] State version mismatch: {ver} (expected {self.STATE_VERSION}). Attempting load.")

        ui = state.get("ui", {})
        rarity = ui.get("rarity", "Uncommon")
        if rarity in RARITIES:
            self.rarity_combo.setCurrentText(rarity)
        self.abs_slider.setValue(int(ui.get("absurdity", 65)))
        self.batch_spin.setValue(int(ui.get("batch", 1)))
        self.slug_edit.setText(ui.get("slug", ""))

        data = state.get("data", {})
        self.generate_iteration = int(data.get("generate_iteration", 0))
        self.lock_enabled = data.get("lock_enabled", {}) or {}
        self.locked_slot_data = data.get("locked_slot_data", {}) or {}
        self.favorites = data.get("favorites", []) or []

        cur = data.get("current_potion", None)
        if isinstance(cur, dict):
            # Display stored potion text directly
            self.rules_view.setPlainText(cur.get("rules_text_md", ""))
            self.player_view.setPlainText(cur.get("player_text", ""))
            self.gm_view.setPlainText(cur.get("gm_notes", ""))
            # Not reconstructing Potion object fully; safe enough for display.
            # New generations will create fresh Potion objects.

        self._render_slots(self.current_potion.slots if self.current_potion else {})
        self._render_favorites()


class _SlotRow(QWidget):
    """
    A small row showing:
      [Lock] Label: value... [Reroll]
    """
    def __init__(self, parent, label: str, key: str, value: str, on_lock_changed, on_reroll_clicked):
        super().__init__(parent)
        self.key = key
        self.on_lock_changed = on_lock_changed
        self.on_reroll_clicked = on_reroll_clicked

        h = QHBoxLayout(self)
        h.setContentsMargins(2, 2, 2, 2)

        self.lock_cb = QCheckBox()
        self.lock_cb.stateChanged.connect(self._lock_changed)
        h.addWidget(self.lock_cb)

        self.label = QLabel(f"{label}:")
        self.label.setFixedWidth(110)
        h.addWidget(self.label)

        self.value = QLabel(value)
        self.value.setWordWrap(True)
        self.value.setTextInteractionFlags(Qt.TextSelectableByMouse)
        h.addWidget(self.value, 1)

        self.btn = QPushButton("Reroll")
        self.btn.setFixedWidth(70)
        self.btn.clicked.connect(lambda: self.on_reroll_clicked(self.key))
        h.addWidget(self.btn)

    def _lock_changed(self, _state):
        self.on_lock_changed(self.key, self.lock_cb.isChecked())
