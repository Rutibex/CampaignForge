from __future__ import annotations

from campaign_forge.core.plugin_api import PluginMeta
from .ui import NpcGenWidget


class NpcGenPlugin:
    meta = PluginMeta(
        plugin_id="npcgen",
        name="NPC Generator",
        version="1.0.0",
        author="Campaign Forge",
        description="Deep, stateful NPC generator with culture packs, roles, relationships, secrets/rumors, and exports.",
        category="Generators",
    )

    def create_widget(self, ctx):
        return NpcGenWidget(ctx)

    # Legacy fallbacks (MainWindow prefers widget-level state)
    def serialize_state(self) -> dict:
        return {}

    def load_state(self, state: dict) -> None:
        return


def load_plugin():
    return NpcGenPlugin()
