
from __future__ import annotations

from PySide6.QtWidgets import QWidget
from campaign_forge.core.plugin_api import PluginMeta
from .ui import RandungeonWidget


class RandungeonPlugin:
    meta = PluginMeta(
        plugin_id="randungeon",
        name="Randungeon (Infinite Table)",
        version="0.1.0",
        author="Rutibex + ChatGPT",
        category="Generators",
        description="Random dungeon key generator driven by depth-based room rarity and classic passage/room tables."
    )

    def create_widget(self, ctx) -> QWidget:
        return RandungeonWidget(ctx)


def load_plugin() -> RandungeonPlugin:
    return RandungeonPlugin()
