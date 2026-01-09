# Contributing to Campaign Forge

Thanks for considering contributing!

## Ways to contribute

- Report bugs (include steps to reproduce + logs)
- Suggest new plugins/modules
- Fix bugs and improve docs
- Add generators, exporters, or UX improvements

## Development setup

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
```

Run:

```bash
python -m campaign_forge.app
```

## Coding guidelines

- **Qt binding:** use **PySide6** only (no PyQt6).
- Keep generator logic Qt-free (prefer `generator.py` modules).
- Keep module state JSON-serializable.
- Don’t crash the app: guard IO/JSON parsing and log recoverable errors with `ctx.log(...)`.
- Prefer deterministic randomness using `ForgeContext` seed helpers.

## Pull requests

- Keep PRs focused and small when possible.
- Include screenshots/GIFs for UI changes.
- Note any state schema changes and add migrations if needed.

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
