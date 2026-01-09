from __future__ import annotations

from PySide6.QtWidgets import QWidget

from campaign_forge.core.plugin_api import PluginMeta
from .ui import TimelineWidget


class TimelinePlugin:
    meta = PluginMeta(
        plugin_id="timeline",
        name="Timeline & Clocks",
        version="0.1.0",
        author="Campaign Forge",
        category="Campaign",
        description="OSR-friendly fronts: clocks that advance on triggers, with a world chronicle log."
    )

    def create_widget(self, ctx) -> QWidget:
        return TimelineWidget(ctx)

    # Widget-first state is preferred; keep plugin state empty for now.
    def serialize_state(self):
        return {}

    def load_state(self, state):
        return None


def load_plugin() -> TimelinePlugin:
    return TimelinePlugin()
