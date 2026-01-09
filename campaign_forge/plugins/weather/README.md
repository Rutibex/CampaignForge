# Weather Almanac Plugin (Campaign Forge)

Drop this folder into:

`campaign_forge/plugins/weather/`

(or merge the contents if you're applying as a patch).

## What it does

- Biome-aware deterministic weather simulation for a full year
- Browse every day, filter by month / search terms
- Overrides (temperature/condition/precip/wind/notes) + optional day locking
- Scratchpad integration (day, month summary, extreme events)
- Export Session Pack (Markdown + CSV + JSON)

## Data Packs

- `tables/biomes.json` — biomes (add your own!)
- `tables/calendars.json` — calendars (add custom fantasy calendars)
- `tables/extremes.json` — rare multi-day extreme events
