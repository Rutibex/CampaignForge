from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional
import csv
import json

from campaign_forge.core.context import ForgeContext


def _safe(s: str) -> str:
    return (s or "").replace("\r\n", "\n").replace("\r", "\n")


def build_year_markdown(year: Dict[str, Any], include_daily: bool = True) -> str:
    cal = year.get("calendar", {})
    biome = year.get("biome", {})
    cfg = year.get("config", {})
    summary = year.get("summary", {})
    days = year.get("days", [])

    lines: List[str] = []
    lines.append(f"# Weather Almanac — {biome.get('name','Biome')} (Year {cfg.get('year_index',0)})")
    lines.append("")
    lines.append("## Configuration")
    lines.append("")
    lines.append(f"- **Calendar:** {cal.get('name','')}")
    lines.append(f"- **Hemisphere:** {cfg.get('hemisphere','north')}")
    lines.append(f"- **Latitude:** {cfg.get('latitude',45)}")
    lines.append(f"- **Elevation:** {cfg.get('elevation_m',0)} m")
    lines.append(f"- **Wetness:** {cfg.get('wetness',1.0)}  |  **Storminess:** {cfg.get('storminess',1.0)}  |  **Extreme Rate:** {cfg.get('extreme_rate',1.0)}")
    lines.append(f"- **Narrative Style:** {cfg.get('narrative_style','Neutral')}")
    lines.append("")

    lines.append("## Year Summary")
    lines.append("")
    lines.append(f"- Avg temp: **{summary.get('avg_temp_c',0):.1f}°C**  (min {summary.get('min_temp_c',0):.1f}°C, max {summary.get('max_temp_c',0):.1f}°C)")
    lines.append(f"- Precipitation days: **{summary.get('precip_days',0)}**")
    lines.append(f"- Storm days: **{summary.get('storm_days',0)}** | Snow days: **{summary.get('snow_days',0)}** | Fog days: **{summary.get('fog_days',0)}**")
    lines.append("")

    lines.append("## Monthly Stats")
    lines.append("")
    lines.append("| Month | Avg °C | Min °C | Max °C | Precip Days | Storm | Snow | Fog |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|")
    for m in summary.get("months", []):
        lines.append(f"| {m.get('month','')} | {m.get('avg_temp_c',0):.1f} | {m.get('min_temp_c',0):.1f} | {m.get('max_temp_c',0):.1f} | {m.get('precip_days',0)} | {m.get('storm_days',0)} | {m.get('snow_days',0)} | {m.get('fog_days',0)} |")
    lines.append("")

    extreme_events = year.get("extreme_events", [])
    if extreme_events:
        lines.append("## Extreme Events")
        lines.append("")
        for e in extreme_events:
            lines.append(f"### {e.get('name', e.get('id','Event'))}")
            lines.append(f"- Days: {e.get('start_day_index')}–{e.get('end_day_index')} (duration {e.get('duration_days')} days)")
            if e.get("effects"):
                lines.append("- Effects:")
                for eff in e["effects"]:
                    lines.append(f"  - {eff}")
            if e.get("note"):
                lines.append(f"- Note: {_safe(e.get('note',''))}")
            lines.append("")

    if include_daily:
        lines.append("## Daily Weather")
        lines.append("")
        for d in days:
            date = d.get("date", {})
            date_str = f"{date.get('month','')} {date.get('day','')}".strip()
            wd = d.get("weekday","")
            cond = d.get("condition","")
            t = d.get("temperature_c", 0.0)
            p = d.get("precip", {})
            w = d.get("wind", {})
            vis = d.get("visibility","")
            daylight = d.get("daylight_hours", 0.0)

            precip = p.get("type","None")
            intensity = p.get("intensity","None")
            precip_str = "Dry" if precip == "None" else f"{precip} ({intensity})"

            wind = f"{w.get('speed_kph',0)} kph {w.get('direction','')}" + (" gusts" if w.get("gusts") else "")
            lines.append(f"### Day {d.get('day_index')} — {date_str} ({wd})")
            lines.append(f"- **Condition:** {cond}")
            lines.append(f"- **Temp:** {t:.1f}°C")
            lines.append(f"- **Precip:** {precip_str}")
            lines.append(f"- **Wind:** {wind}")
            lines.append(f"- **Visibility:** {vis} | **Daylight:** {daylight:.1f}h")
            if d.get("notes"):
                lines.append(f"- **Notes:** {_safe(d.get('notes',''))}")
            if d.get("narrative"):
                lines.append("")
                lines.append(_safe(d.get("narrative","")))
            lines.append("")
    return "\n".join(lines).strip() + "\n"


def build_monthly_summary_markdown(year: Dict[str, Any]) -> str:
    cal = year.get("calendar", {})
    biome = year.get("biome", {})
    cfg = year.get("config", {})
    summary = year.get("summary", {})
    lines: List[str] = []
    lines.append(f"# Monthly Weather Summary — {biome.get('name','Biome')} (Year {cfg.get('year_index',0)})")
    lines.append("")
    for m in summary.get("months", []):
        lines.append(f"## {m.get('month','')}")
        lines.append(f"- Avg temp: {m.get('avg_temp_c',0):.1f}°C (min {m.get('min_temp_c',0):.1f}°C, max {m.get('max_temp_c',0):.1f}°C)")
        lines.append(f"- Precip days: {m.get('precip_days',0)} | Storm: {m.get('storm_days',0)} | Snow: {m.get('snow_days',0)} | Fog: {m.get('fog_days',0)}")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def build_csv_rows(year: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for d in year.get("days", []):
        date = d.get("date", {})
        precip = d.get("precip", {})
        wind = d.get("wind", {})
        rows.append({
            "day_index": d.get("day_index"),
            "weekday": d.get("weekday"),
            "month": date.get("month"),
            "day": date.get("day"),
            "temperature_c": round(float(d.get("temperature_c", 0.0)), 2),
            "condition": d.get("condition"),
            "precip_type": precip.get("type"),
            "precip_intensity": precip.get("intensity"),
            "wind_kph": wind.get("speed_kph"),
            "wind_dir": wind.get("direction"),
            "gusts": wind.get("gusts"),
            "visibility": d.get("visibility"),
            "daylight_hours": round(float(d.get("daylight_hours", 0.0)), 2),
            "notes": _safe(d.get("notes","")),
            "tags": ",".join(d.get("tags", [])),
        })
    return rows


def export_year_pack(ctx: ForgeContext, year: Dict[str, Any], slug: str, seed: int, include_daily_md: bool = True) -> Path:
    pack_dir = ctx.export_manager.create_session_pack("weather", slug=slug, seed=seed)
    # Markdown
    year_md = build_year_markdown(year, include_daily=include_daily_md)
    (pack_dir / "weather_year.md").write_text(year_md, encoding="utf-8")
    (pack_dir / "monthly_summary.md").write_text(build_monthly_summary_markdown(year), encoding="utf-8")

    # CSV
    rows = build_csv_rows(year)
    csv_path = pack_dir / "weather_year.csv"
    if rows:
        with csv_path.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)

    # JSON
    (pack_dir / "weather_year.json").write_text(json.dumps(year, indent=2, ensure_ascii=False), encoding="utf-8")

    return pack_dir
