from __future__ import annotations

from campaign_forge.core.plugin_api import PluginMeta
from .ui import PlanetGenWidget


class PlanetGenPlugin:
    meta = PluginMeta(
        plugin_id="planetgen",
        name="Planet Generator",
        version="1.0.0",
        author="Campaign Forge",
        description="Generate a deterministic planet with terrain, climate, biomes, factions, settlements, POIs, and exports.",
        category="Worldbuilding",
    )

    def create_widget(self, ctx):
        return PlanetGenWidget(ctx)


def load_plugin():
    return PlanetGenPlugin()
