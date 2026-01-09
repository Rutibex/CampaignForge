from campaign_forge.core.plugin_api import PluginMeta
from .ui import PantheonWidget


class PantheonPlugin:
    meta = PluginMeta(
        plugin_id="pantheon",
        name="Pantheon Generator",
        version="1.0.0",
        category="Generators",
    )

    def create_widget(self, ctx):
        return PantheonWidget(ctx)


def load_plugin():
    return PantheonPlugin()
