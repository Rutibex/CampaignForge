from __future__ import annotations
from typing import Dict, Any

from PySide6.QtWidgets import QWidget
from campaign_forge.core.plugin_api import PluginMeta
from .ui import NamesWidget

class NamesPlugin:
    meta = PluginMeta(
        plugin_id="names",
        name="Names",
        version="0.1.0",
        author="Rutibex",
        category="Generators",
        description="Local name generator with simple style profiles."
    )

    def __init__(self):
        self._state: Dict[str, Any] = {}

    def create_widget(self, ctx) -> QWidget:
        return NamesWidget(ctx)

    def serialize_state(self) -> Dict[str, Any]:
        # later: persist user settings
        return dict(self._state)

    def load_state(self, state: Dict[str, Any]) -> None:
        self._state = dict(state or {})

def load_plugin() -> NamesPlugin:
    return NamesPlugin()
