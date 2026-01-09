# Campaign Forge

Campaign Forge is a **desktop GM content engine** built with **Python + PySide6**. It provides a modular plugin system for procedural generators (hex maps, dungeon maps, names, etc.) plus cross-module services like project persistence, exports, tagging, and a global scratchpad.

> **Qt binding:** This project uses **PySide6** (not PyQt6).

## Features

- **Plugin-based modules**: independent UI tools under `campaign_forge/plugins/*`
- **Multiple projects/campaigns**: each with its own exports + module state
- **Deterministic RNG**: reproducible outputs from a master seed + derived seeds
- **Session pack exports**: predictable folders for maps/keys/notes
- **Global scratchpad**: tagged note capture with search & filtering
- **Fault-tolerant plugin loading**: one broken plugin won’t brick the app

## Screenshots

Add screenshots/gifs here (recommended). For example:

- `docs/screenshots/main_window.png`
- `docs/screenshots/dungeonmap.png`

## Quickstart

### 1) Requirements

- Python 3.10+ recommended
- Windows / macOS / Linux

### 2) Install dependencies

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
```

### 3) Run

From the repository root:

```bash
python -m campaign_forge.app
```

On Windows you can also run:

- `run_campaign_forge.bat`

## Project layout

### Application package

```
campaign_forge/
  campaign_forge/
    app.py
    core/
    ui/
    plugins/
  run_campaign_forge.bat
```

### Per-project structure

Each project/campaign is a folder that contains (created automatically):

```
<project_root>/
  project.json
  exports/
    session_packs/
  themes/
  modules/
    <plugin_id>.json
    _scratchpad.json
```

## Plugin development

Plugins live in `campaign_forge/campaign_forge/plugins/<your_plugin>/`.

Minimal `plugin.py`:

```python
from campaign_forge.core.plugin_api import PluginMeta
from .ui import MyPluginWidget

class MyPlugin:
    meta = PluginMeta(
        plugin_id="myplugin",
        name="My Plugin",
        version="0.1.0",
        category="Generators",
    )

    def create_widget(self, ctx):
        return MyPluginWidget(ctx)

def load_plugin():
    return MyPlugin()
```

Recommended widget methods:

- `serialize_state() -> dict`
- `load_state(state: dict) -> None`

See existing plugins (`names`, `hexmap`, `dungeonmap`) for patterns.

## Contributing

Contributions are welcome! Please read:

- `CONTRIBUTING.md`
- `CODE_OF_CONDUCT.md`

## License

MIT — see `LICENSE`.
