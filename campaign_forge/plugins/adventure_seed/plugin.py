from __future__ import annotations
from typing import Dict, Any

from PySide6.QtWidgets import QWidget
from campaign_forge.core.plugin_api import PluginMeta
from .ui import AdventureSeedWidget


class AdventureSeedPlugin:
    meta = PluginMeta(
        plugin_id="adventure_seed",
        name="Adventure Seed Engine",
        version="0.1.0",
        author="Campaign Forge",
        category="Generators",
        description="One-click 'tonight's adventure' generator (hook, location, antagonist, twist, countdown clock)."
    )

    def __init__(self):
        self._state: Dict[str, Any] = {}

    def create_widget(self, ctx) -> QWidget:
        return AdventureSeedWidget(ctx)

    # These are not used by the app if widget handles state, but kept for compatibility.
    def serialize_state(self) -> Dict[str, Any]:
        return dict(self._state)

    def load_state(self, state: Dict[str, Any]) -> None:
        self._state = dict(state or {})


def load_plugin() -> AdventureSeedPlugin:
    return AdventureSeedPlugin()
