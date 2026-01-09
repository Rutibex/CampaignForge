from __future__ import annotations
from typing import Dict, Any

from PySide6.QtWidgets import QWidget
from campaign_forge.core.plugin_api import PluginMeta
from .ui import LocationStackWidget


class LocationStackPlugin:
    meta = PluginMeta(
        plugin_id="location_stack",
        name="Location Stack",
        version="0.1.1",
        author="Campaign Forge",
        category="Generators",
        description="Generate a linked Region → Site → Sub-site → Room stack (with optional dungeon, faction, rumors)."
    )

    def __init__(self):
        self._state: Dict[str, Any] = {}

    def create_widget(self, ctx) -> QWidget:
        return LocationStackWidget(ctx)

    def serialize_state(self) -> Dict[str, Any]:
        return dict(self._state)

    def load_state(self, state: Dict[str, Any]) -> None:
        self._state = dict(state or {})


def load_plugin() -> LocationStackPlugin:
    return LocationStackPlugin()
