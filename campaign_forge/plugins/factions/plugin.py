from __future__ import annotations
from typing import Dict, Any

from PySide6.QtWidgets import QWidget

from campaign_forge.core.plugin_api import PluginMeta
from .ui import FactionsWidget


class FactionsPlugin:
    meta = PluginMeta(
        plugin_id="factions",
        name="Factions",
        version="0.1.0",
        author="Rutibex",
        category="Worldbuilding",
        description="Faction / organization builder with goals, assets, schisms, timeline, exports."
    )

    def __init__(self) -> None:
        self._state: Dict[str, Any] = {}

    def create_widget(self, ctx) -> QWidget:
        return FactionsWidget(ctx)

    # legacy (not used if widget implements serialize_state/load_state)
    def serialize_state(self) -> Dict[str, Any]:
        return dict(self._state)

    def load_state(self, state: Dict[str, Any]) -> None:
        self._state = dict(state or {})


def load_plugin() -> FactionsPlugin:
    return FactionsPlugin()
