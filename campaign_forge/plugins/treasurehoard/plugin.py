from __future__ import annotations

from typing import Dict, Any

from PySide6.QtWidgets import QWidget

from campaign_forge.core.plugin_api import PluginMeta
from .ui import TreasureHoardWidget


class TreasureHoardPlugin:
    meta = PluginMeta(
        plugin_id="treasurehoard",
        name="Treasure Hoard",
        version="1.0.0",
        author="Rutibex",
        category="Generators",
        description="Scalable treasure hoard generator: coins, gems, art, commodities, magic, scrolls, relics, containers, and complications."
    )

    def __init__(self) -> None:
        self._state: Dict[str, Any] = {}

    def create_widget(self, ctx) -> QWidget:
        return TreasureHoardWidget(ctx)

    def serialize_state(self) -> Dict[str, Any]:
        # Widget-level state is preferred; plugin-level state kept for compatibility.
        return dict(self._state)

    def load_state(self, state: Dict[str, Any]) -> None:
        self._state = dict(state or {})


def load_plugin() -> TreasureHoardPlugin:
    return TreasureHoardPlugin()
