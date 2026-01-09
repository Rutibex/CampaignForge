from __future__ import annotations

from campaign_forge.core.plugin_api import PluginMeta
from .ui import ContinentMapWidget


class ContinentMapPlugin:
    meta = PluginMeta(
        plugin_id="continentmap",
        name="Continent Map + Factions",
        version="0.1.0",
        author="Campaign Forge",
        description="Generate a continental terrain map with faction territory overlays and exports.",
        category="Generators",
    )

    def create_widget(self, ctx):
        return ContinentMapWidget(ctx)

    # Legacy fallbacks (MainWindow prefers widget state)
    def serialize_state(self):
        return {"version": 1, "state": {}}

    def load_state(self, state):
        pass


def load_plugin():
    return ContinentMapPlugin()
