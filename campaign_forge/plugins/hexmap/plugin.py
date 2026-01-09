from __future__ import annotations
from typing import Dict, Any

from PySide6.QtWidgets import QWidget
from campaign_forge.core.plugin_api import PluginMeta
from .ui import HexMapWidget


class HexMapPlugin:
    meta = PluginMeta(
        plugin_id="hexmap",
        name="Hex Map",
        version="0.1.0",
        author="Rutibex",
        category="Generators",
        description="Procedural hex map generator with PNG + Markdown exports."
    )

    def __init__(self):
        self._state: Dict[str, Any] = {}

    def create_widget(self, ctx) -> QWidget:
        return HexMapWidget(ctx)

    def serialize_state(self) -> Dict[str, Any]:
        return dict(self._state)

    def load_state(self, state: Dict[str, Any]) -> None:
        self._state = dict(state or {})


def load_plugin() -> HexMapPlugin:
    return HexMapPlugin()
