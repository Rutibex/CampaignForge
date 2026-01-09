# Solar System Generator (Campaign Forge Plugin)

Drop this folder into:

`campaign_forge/plugins/solarsystem/`

Then restart Campaign Forge.

## What it does

- Generates deterministic star systems (stars, planets, moons, belts)
- Opens a dedicated **orbital map window** (pan/zoom, click to select)
- Produces **Traveller-style summaries** for life-bearing and inhabited worlds
- Exports a session pack (PNG + SVG map + markdown dossiers + JSON)

## Notes

- Uses Campaign Forge's `ForgeContext` RNG if available (`ctx.derive_rng`).
- Falls back to local deterministic RNG if needed.
- Scratchpad integration is optional (`ctx.scratchpad_add`).

## Tables / starting content

See `tables/` for:
- star types
- planet classes
- biospheres
- cultures/governments
- hazards
- trade goods
- name syllables
- seed presets
