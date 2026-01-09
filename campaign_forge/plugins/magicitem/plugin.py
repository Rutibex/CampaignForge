from campaign_forge.core.plugin_api import PluginMeta
from .ui import MagicItemWidget


class MagicItemPlugin:
    meta = PluginMeta(
        plugin_id="magicitem",
        name="Magic Item Generator",
        version="1.0.0",
        category="Generators",
    )

    def create_widget(self, ctx):
        return MagicItemWidget(ctx)


def load_plugin():
    return MagicItemPlugin()
