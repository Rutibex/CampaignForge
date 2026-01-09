# campaign_forge/plugins/monstergen/plugin.py

from campaign_forge.core.plugin_api import PluginMeta
from .ui import MonsterGenWidget


class MonsterGenPlugin:
    meta = PluginMeta(
        plugin_id="monstergen",
        name="Monster Generator (5e)",
        version="1.0.0",
        category="Generators",
    )

    def create_widget(self, ctx):
        return MonsterGenWidget(ctx)


def load_plugin():
    return MonsterGenPlugin()
