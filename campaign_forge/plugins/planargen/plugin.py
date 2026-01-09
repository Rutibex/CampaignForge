# =========================
# campaign_forge/plugins/planargen/plugin.py
# =========================
from campaign_forge.core.plugin_api import PluginMeta
from .ui import PlanarGeneratorWidget


class PlanarGeneratorPlugin:
    meta = PluginMeta(
        plugin_id="planargen",
        name="Planar Generator",
        version="1.0.0",
        category="Generators",
    )

    def create_widget(self, ctx):
        return PlanarGeneratorWidget(ctx)


def load_plugin():
    return PlanarGeneratorPlugin()
