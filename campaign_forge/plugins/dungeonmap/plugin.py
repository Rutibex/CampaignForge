from __future__ import annotations
from typing import Dict, Any
from PySide6.QtWidgets import QWidget

from campaign_forge.core.plugin_api import PluginMeta
from .ui import DungeonMapWidget


class DungeonMapPlugin:
    meta = PluginMeta(
        plugin_id="dungeonmap",
        name="Dungeon Map",
        version="0.1.0",
        author="Rutibex",
        category="Generators",
        description="Seeded room-and-corridor dungeon map generator with export."
    )

    def __init__(self):
        self._state: Dict[str, Any] = {}

    def create_widget(self, ctx) -> QWidget:
        return DungeonMapWidget(ctx)

    def serialize_state(self) -> Dict[str, Any]:
        return dict(self._state)

    def load_state(self, state: Dict[str, Any]) -> None:
        self._state = dict(state or {})


def load_plugin() -> DungeonMapPlugin:
    return DungeonMapPlugin()
