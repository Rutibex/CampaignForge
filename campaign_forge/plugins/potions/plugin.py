# campaign_forge/plugins/potions/plugin.py

from campaign_forge.core.plugin_api import PluginMeta
from .ui import PotionGeneratorWidget


class PotionPlugin:
    meta = PluginMeta(
        plugin_id="potions",
        name="Potion Generator",
        version="1.0.0",
        category="Generators",
    )

    def create_widget(self, ctx):
        return PotionGeneratorWidget(ctx)


def load_plugin():
    return PotionPlugin()
