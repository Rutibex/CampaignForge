from __future__ import annotations
import importlib
import pkgutil
from dataclasses import dataclass
from typing import List, Optional

from .plugin_api import ForgePlugin

@dataclass
class LoadedPlugin:
    package: str           # e.g. "plugins.names"
    plugin: ForgePlugin

class PluginManager:
    """
    Discovers plugins under the `plugins` package.
    A plugin is a package containing `plugin.py` with load_plugin().
    """
    def __init__(self, plugins_pkg: str | None = None):
        base_pkg = __package__.split(".")[0]  # "campaign_forge"
        self.plugins_pkg = plugins_pkg or f"{base_pkg}.plugins"
        self._loaded: List[LoadedPlugin] = []


    def discover_and_load(self) -> List[LoadedPlugin]:
        self._loaded.clear()

        pkg = importlib.import_module(self.plugins_pkg)
        for mod in pkgutil.iter_modules(pkg.__path__, pkg.__name__ + "."):
            # Only consider packages (folders); ignore single .py modules
            if not mod.ispkg:
                continue

            plugin_module_name = mod.name + ".plugin"  # plugins.names.plugin
            try:
                plugin_mod = importlib.import_module(plugin_module_name)
            except Exception as e:
                print(f"[PluginManager] Failed to import {plugin_module_name}: {e}")
                continue

            if not hasattr(plugin_mod, "load_plugin"):
                print(f"[PluginManager] {plugin_module_name} has no load_plugin()")
                continue

            try:
                plugin = plugin_mod.load_plugin()
                self._loaded.append(LoadedPlugin(package=mod.name, plugin=plugin))
            except Exception as e:
                print(f"[PluginManager] Failed to load plugin from {plugin_module_name}: {e}")

        # Stable ordering: category then name
        self._loaded.sort(key=lambda lp: (getattr(lp.plugin.meta, "category", ""), lp.plugin.meta.name))
        return list(self._loaded)

    @property
    def loaded(self) -> List[LoadedPlugin]:
        return list(self._loaded)

    def get_by_id(self, plugin_id: str) -> Optional[LoadedPlugin]:
        for lp in self._loaded:
            if lp.plugin.meta.plugin_id == plugin_id:
                return lp
        return None
