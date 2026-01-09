from __future__ import annotations

from typing import Dict, Any
from PySide6.QtWidgets import QWidget

from campaign_forge.core.plugin_api import PluginMeta
from .ui import SolarSystemWidget


class SolarSystemPlugin:
    meta = PluginMeta(
        plugin_id="solarsystem",
        name="Solar System",
        version="1.0.0",
        author="Campaign Forge",
        category="Generators",
        description="Deterministic solar system generator with orbital map and Traveller-style world summaries."
    )

    def __init__(self) -> None:
        self._state: Dict[str, Any] = {}

    def create_widget(self, ctx) -> QWidget:
        return SolarSystemWidget(ctx)

    # Plugin-level state is optional; we keep minimal here.
    def serialize_state(self) -> Dict[str, Any]:
        return dict(self._state)

    def load_state(self, state: Dict[str, Any]) -> None:
        self._state = dict(state or {})


def load_plugin() -> SolarSystemPlugin:
    return SolarSystemPlugin()
