from __future__ import annotations

from campaign_forge.core.plugin_api import PluginMeta
from .ui import EncounterGeneratorWidget


class EncounterGeneratorPlugin:
    meta = PluginMeta(
        plugin_id="encounters",
        name="Encounter Generator",
        version="1.0.0",
        author="Campaign Forge",
        description="Context-aware 5e encounter generator with tactics, morale, environment, and exports.",
        category="Generators",
    )

    def create_widget(self, ctx):
        return EncounterGeneratorWidget(ctx)

    # Legacy (unused) - MainWindow prefers widget-level state
    def serialize_state(self):
        return {}

    def load_state(self, state):
        return


def load_plugin():
    return EncounterGeneratorPlugin()
