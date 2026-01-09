from __future__ import annotations
from dataclasses import dataclass
from typing import Protocol, Optional, Dict, Any
from PySide6.QtWidgets import QWidget
from .context import ForgeContext

@dataclass(frozen=True)
class PluginMeta:
    plugin_id: str          # stable id, e.g. "names"
    name: str               # display name, e.g. "Names"
    version: str = "0.1.0"
    author: str = "You"
    description: str = ""
    category: str = "General"
    icon: str = ""          # optional icon path later

class ForgePlugin(Protocol):
    """
    Minimal interface every plugin implements.
    Keep it tiny so adding new modules is frictionless.
    """
    meta: PluginMeta

    def create_widget(self, ctx: ForgeContext) -> QWidget:
        ...

    def serialize_state(self) -> Dict[str, Any]:
        ...

    def load_state(self, state: Dict[str, Any]) -> None:
        ...

def load_plugin() -> ForgePlugin:
    """
    Each plugin package must expose a load_plugin() function in plugin.py.
    """
    raise NotImplementedError
