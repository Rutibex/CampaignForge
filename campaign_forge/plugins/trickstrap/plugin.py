from campaign_forge.core.plugin_api import PluginMeta
from .ui import TricksAndTrapsWidget


class TricksAndTrapsPlugin:
    meta = PluginMeta(
        plugin_id="trickstrap",
        name="Tricks & Traps (Ad-Lib Generator)",
        version="1.0.0",
        category="Generators",
    )

    def create_widget(self, ctx):
        return TricksAndTrapsWidget(ctx)


def load_plugin():
    return TricksAndTrapsPlugin()
