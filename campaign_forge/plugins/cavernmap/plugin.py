# -------------------------
# plugin.py
# -------------------------
from campaign_forge.core.plugin_api import PluginMeta
from .ui import CavernMapWidget

class CavernMapPlugin:
    meta = PluginMeta(
        plugin_id="cavernmap",
        name="Cavern Generator",
        version="1.0.0",
        category="Generators",
    )

    def create_widget(self, ctx):
        return CavernMapWidget(ctx)

def load_plugin():
    return CavernMapPlugin()