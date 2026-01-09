
from __future__ import annotations
from campaign_forge.core.plugin_api import PluginMeta
from .ui import SettlementWidget

class SettlementPlugin:
    meta = PluginMeta(
        plugin_id="settlement",
        name="Settlement / Town Generator",
        version="1.0.0",
        author="Campaign Forge",
        description="Generate OSR-friendly settlements with factions, districts, locations, rumors, and an exportable map.",
        category="Generators",
    )

    def create_widget(self, ctx):
        return SettlementWidget(ctx)

def load_plugin():
    return SettlementPlugin()
