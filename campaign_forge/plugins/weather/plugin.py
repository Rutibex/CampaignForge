from __future__ import annotations

from campaign_forge.core.plugin_api import PluginMeta
from .ui import WeatherWidget


class WeatherPlugin:
    meta = PluginMeta(
        plugin_id="weather",
        name="Weather Almanac",
        version="1.0.0",
        author="Campaign Forge",
        description="Biome-aware, deterministic weather simulation for a full year with daily inspection, overrides, and exports.",
        category="Worldbuilding",
    )

    def create_widget(self, ctx):
        return WeatherWidget(ctx)


def load_plugin():
    return WeatherPlugin()
