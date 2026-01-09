from __future__ import annotations

from campaign_forge.core.plugin_api import PluginMeta
from .ui import ArtifactWidget


class ArtifactsPlugin:
    meta = PluginMeta(
        plugin_id="artifacts",
        name="Artifacts",
        version="1.0.0",
        author="Campaign Forge",
        category="Generators",
        description="Generate exotic relics and artifacts with 5e-compatible mechanics, costs, and lore hooks.",
    )

    def create_widget(self, ctx):
        return ArtifactWidget(ctx)


def load_plugin():
    return ArtifactsPlugin()
