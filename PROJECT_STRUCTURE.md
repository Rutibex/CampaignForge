# Project Structure

This document summarizes the important folders and conventions used by Campaign Forge.

## App package

- `campaign_forge/campaign_forge/app.py` — app boot
- `campaign_forge/campaign_forge/ui/` — main window + scratchpad UI
- `campaign_forge/campaign_forge/core/` — context, plugin API, plugin manager, export manager
- `campaign_forge/campaign_forge/plugins/` — built-in plugins

## Per-project folders (created under a project root)

- `project.json` — master seed and project settings
- `exports/` — exported artifacts
- `exports/session_packs/` — one folder per generation/export drop
- `themes/` — optional theme packs
- `modules/` — saved per-plugin state + scratchpad state
