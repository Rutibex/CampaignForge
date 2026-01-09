# Factions Plugin

A Campaign Forge module for building living factions / organizations.

## Features (v0.1.0)
- Multiple factions per project
- Overview fields: name, type, ethos, threat, tone, motto, public face, hidden truth, tags, notes
- Goals, Assets, Relationships, Schisms, Timeline tables
- Deterministic generators (Generate Faction / Goal / Asset / Schism / Event)
- "Advance Clocks" button to nudge goals/schisms and create a timeline event
- Exports:
  - Session pack containing GM + player-redacted markdown
  - GM-only export
  - Player-only export
- Send GM summary to Scratchpad

State is stored per-project at:
`<project>/modules/factions.json`
