from __future__ import annotations

from pathlib import Path
from typing import Dict, Any, List, Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QListWidget, QListWidgetItem,
    QStackedWidget, QTextEdit, QHBoxLayout, QVBoxLayout, QLabel, QSplitter,
    QTabWidget, QFileDialog, QInputDialog, QMessageBox
)

from campaign_forge.core.context import ForgeContext
from campaign_forge.core.plugin_manager import PluginManager, LoadedPlugin
from campaign_forge.core.app_settings import AppSettings
from campaign_forge.ui.scratchpad import ScratchpadWidget, ScratchpadEntry


STATE_SAVE_INTERVAL_MS = 30_000  # 30s


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Campaign Forge")

        self.settings = AppSettings()

        # Context + services (wired to UI)
        self.ctx = ForgeContext()

        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setPlaceholderText("Logs…")

        def ui_log(msg: str) -> None:
            self.log_view.append(msg)

        self.ctx.log = ui_log

        # Scratchpad (project-persisted)
        self.scratchpad = ScratchpadWidget()
        self.scratchpad.changed.connect(self._save_scratchpad)

        def scratchpad_add(text: str, tags=None) -> None:
            self.scratchpad.add_entry(text, tags)

        self.ctx.scratchpad_add = scratchpad_add

        # Modules UI
        self.module_list = QListWidget()
        self.module_list.setMinimumWidth(220)

        self.stack = QStackedWidget()

        # Tabs: Module + Scratchpad
        self.tabs = QTabWidget()
        self.tabs.addTab(self.stack, "Module")
        self.tabs.addTab(self.scratchpad, "Scratchpad")

        # Left panel
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(8, 8, 8, 8)
        left_layout.addWidget(QLabel("Modules"))
        left_layout.addWidget(self.module_list)

        # Right panel
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(8, 8, 8, 8)
        right_layout.addWidget(self.tabs, stretch=4)
        right_layout.addWidget(QLabel("Log"))
        right_layout.addWidget(self.log_view, stretch=1)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        central = QWidget()
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(splitter)
        self.setCentralWidget(central)

        # Menu
        self._build_menu()

        # Plugins
        self.plugin_manager = PluginManager()
        self.loaded: List[LoadedPlugin] = []
        self.module_widgets: Dict[str, QWidget] = {}

        self.module_list.currentRowChanged.connect(self._on_module_changed)

        # State persistence timer
        self._save_timer = QTimer(self)
        self._save_timer.setInterval(STATE_SAVE_INTERVAL_MS)
        self._save_timer.timeout.connect(self.save_all_state)
        self._save_timer.start()

        # Choose project (from settings or default)
        self._load_initial_project()

        # Restore window geometry if present
        geom = self.settings.get_window_geometry()
        if geom:
            try:
                self.restoreGeometry(geom)
            except Exception:
                pass

    # ---------- menu / project selection ----------

    def _build_menu(self) -> None:
        mb = self.menuBar()
        file_menu = mb.addMenu("File")

        act_new = QAction("New Project…", self)
        act_open = QAction("Open Project…", self)
        act_save = QAction("Save", self)
        act_quit = QAction("Quit", self)

        act_new.triggered.connect(self._new_project)
        act_open.triggered.connect(self._open_project)
        act_save.triggered.connect(self.save_all_state)
        act_quit.triggered.connect(self.close)

        file_menu.addAction(act_new)
        file_menu.addAction(act_open)
        file_menu.addSeparator()
        file_menu.addAction(act_save)
        file_menu.addSeparator()
        file_menu.addAction(act_quit)

    def _load_initial_project(self) -> None:
        last = self.settings.get_last_project_dir()
        if last and last.exists():
            self.set_project(last)
            return

        # Default to bundled projects/default_project relative to CWD if it exists; otherwise create it.
        default = Path.cwd() / "projects" / "default_project"
        default.mkdir(parents=True, exist_ok=True)
        self.set_project(default)

    def _new_project(self) -> None:
        parent_dir = QFileDialog.getExistingDirectory(self, "Choose parent folder for new project")
        if not parent_dir:
            return

        name, ok = QInputDialog.getText(self, "New Project", "Project name:")
        if not ok:
            return
        name = (name or "").strip()
        if not name:
            QMessageBox.warning(self, "New Project", "Project name cannot be empty.")
            return

        proj_dir = Path(parent_dir) / name
        if proj_dir.exists() and any(proj_dir.iterdir()):
            QMessageBox.warning(self, "New Project", "That folder already exists and is not empty.")
            return

        proj_dir.mkdir(parents=True, exist_ok=True)
        self.set_project(proj_dir)

    def _open_project(self) -> None:
        proj_dir = QFileDialog.getExistingDirectory(self, "Open Project")
        if not proj_dir:
            return
        self.set_project(Path(proj_dir))

    def set_project(self, proj_dir: Path) -> None:
        # Save current state before switching
        try:
            self.save_all_state()
        except Exception:
            pass

        proj_dir = Path(proj_dir)
        self.ctx.set_project_dir(proj_dir)
        self.settings.set_last_project_dir(proj_dir)

        # Update title
        pname = str(self.ctx.project_settings.get("name", proj_dir.name))
        self.setWindowTitle(f"Campaign Forge — {pname}")

        self.ctx.log(f"Project: {proj_dir}")

        # Load scratchpad for this project
        self._load_scratchpad()

        # Load/reload plugins + state
        self._load_plugins()

    # ---------- plugin loading + state persistence ----------

    def _load_plugins(self) -> None:
        # Clear UI
        self.module_list.blockSignals(True)
        self.module_list.clear()
        self.module_list.blockSignals(False)

        # QStackedWidget has no clear(); remove pages manually
        while self.stack.count() > 0:
            w = self.stack.widget(0)
            self.stack.removeWidget(w)
            try:
                w.deleteLater()
            except Exception:
                pass
        self.loaded.clear()
        self.module_widgets.clear()

        # Load plugins
        self.loaded = self.plugin_manager.discover_and_load()

        failed = 0
        for lp in self.loaded:
            meta = lp.plugin.meta
            try:
                w = lp.plugin.create_widget(self.ctx)
            except Exception as e:
                failed += 1
                self.ctx.log(f"[Plugin] Failed to load {meta.plugin_id} ({meta.name}): {e}")
                continue

            item = QListWidgetItem(meta.name)
            self.module_list.addItem(item)

            self.stack.addWidget(w)
            self.module_widgets[meta.plugin_id] = w

            # Load module widget state (preferred)
            self._load_module_state(meta.plugin_id, w)

        ok = len(self.module_widgets)
        self.ctx.log(f"Loaded {ok} modules." + (f" ({failed} failed)" if failed else ""))
        for lp in self.loaded:
            self.ctx.log(f" - {lp.plugin.meta.plugin_id}: {lp.plugin.meta.name} ({lp.plugin.meta.version})")

        if self.module_list.count() > 0:
            self.module_list.setCurrentRow(0)

    def _module_state_path(self, plugin_id: str) -> str:
        return f"modules/{plugin_id}.json"

    def _load_module_state(self, plugin_id: str, widget: QWidget) -> None:
        data = self.ctx.load_json(self._module_state_path(plugin_id), default=None)
        if not data:
            return

        # Widget-level state (recommended)
        if hasattr(widget, "load_state") and callable(getattr(widget, "load_state")):
            try:
                widget.load_state(data)
                return
            except Exception as e:
                self.ctx.log(f"[State] Failed to load state into widget {plugin_id}: {e}")

        # Fallback: plugin-level state (legacy)
        lp = self.plugin_manager.get_by_id(plugin_id)
        if lp:
            try:
                lp.plugin.load_state(data)
            except Exception as e:
                self.ctx.log(f"[State] Failed to load state into plugin {plugin_id}: {e}")

    def _save_module_state(self, plugin_id: str, widget: QWidget) -> None:
        state: Optional[Dict[str, Any]] = None

        if hasattr(widget, "serialize_state") and callable(getattr(widget, "serialize_state")):
            try:
                state = widget.serialize_state()
            except Exception as e:
                self.ctx.log(f"[State] Failed to serialize state from widget {plugin_id}: {e}")
                state = None
        else:
            # fallback to plugin serialize_state
            lp = self.plugin_manager.get_by_id(plugin_id)
            if lp:
                try:
                    state = lp.plugin.serialize_state()
                except Exception as e:
                    self.ctx.log(f"[State] Failed to serialize state from plugin {plugin_id}: {e}")
                    state = None

        if state is None:
            return
        self.ctx.save_json(self._module_state_path(plugin_id), state)

    def save_all_state(self) -> None:
        # Project settings
        try:
            self.ctx.save_project_settings()
        except Exception as e:
            self.ctx.log(f"[State] Failed to save project settings: {e}")

        # Module states
        for lp in self.loaded:
            pid = lp.plugin.meta.plugin_id
            w = self.module_widgets.get(pid)
            if w:
                try:
                    self._save_module_state(pid, w)
                except Exception as e:
                    self.ctx.log(f"[State] Failed saving {pid}: {e}")

        # Scratchpad
        try:
            self._save_scratchpad()
        except Exception as e:
            self.ctx.log(f"[State] Failed saving scratchpad: {e}")

    # ---------- scratchpad persistence ----------

    def _scratchpad_path(self) -> str:
        return "modules/_scratchpad.json"

    def _load_scratchpad(self) -> None:
        data = self.ctx.load_json(self._scratchpad_path(), default=[])
        self.scratchpad.load_json(data)

    def _save_scratchpad(self) -> None:
        self.ctx.save_json(self._scratchpad_path(), self.scratchpad.to_json())

    # ---------- events ----------

    def closeEvent(self, event) -> None:
        try:
            self.save_all_state()
        except Exception:
            pass
        try:
            self.settings.set_window_geometry(self.saveGeometry())
        except Exception:
            pass
        super().closeEvent(event)

    def _on_module_changed(self, row: int) -> None:
        if row < 0 or row >= self.stack.count():
            return
        self.stack.setCurrentIndex(row)
        item = self.module_list.item(row)
        if item:
            self.ctx.log(f"Switched to module: {item.text()}")
