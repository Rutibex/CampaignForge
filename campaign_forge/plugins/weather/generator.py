from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
import math
import random
from pathlib import Path
import json


# ----------------------------
# Data models
# ----------------------------

@dataclass
class CalendarConfig:
    """Simple calendar configuration.

    - months: list of month names
    - days_in_month: list of int, same length as months
    """
    calendar_id: str
    name: str
    months: List[str]
    days_in_month: List[int]
    weekday_names: List[str]

    @property
    def days_per_year(self) -> int:
        return int(sum(self.days_in_month))


@dataclass
class WeatherConfig:
    biome_id: str = "temperate_forest"
    year_index: int = 0
    calendar_id: str = "gregorian_365"
    hemisphere: str = "north"  # north/south
    latitude: float = 45.0     # for flavor & temp curve
    elevation_m: float = 0.0   # affects temp
    anomaly: float = 0.0       # -2..+2 approx (cold/hot year)
    storminess: float = 1.0    # 0.5..2.0
    wetness: float = 1.0       # 0.5..2.0
    extreme_rate: float = 1.0  # 0.0..2.0
    narrative_style: str = "Neutral"
    generate_narrative: bool = True


# ----------------------------
# Helpers
# ----------------------------

def _clamp(x: float, a: float, b: float) -> float:
    return max(a, min(b, x))


def _seasonal_t(day_of_year: int, days_per_year: int, hemisphere: str) -> float:
    """
    Returns a smooth seasonal value in [-1, 1] where:
    -1 ~ coldest, +1 ~ warmest.
    """
    # Peak warmth around day ~ 200 in northern hemisphere (approx)
    phase = 2 * math.pi * (day_of_year / max(1, days_per_year))
    # Shift so that phase=0 is winter-ish
    # We'll align warm peak roughly mid-year.
    base = math.sin(phase - math.pi / 2)  # -1 at day 0, +1 at mid-year
    if hemisphere.lower().startswith("s"):
        base = -base
    return float(base)


def _fmt_temp(c: float, unit: str = "C") -> str:
    if unit.upper() == "F":
        f = c * 9.0 / 5.0 + 32.0
        return f"{f:.0f}°F"
    return f"{c:.0f}°C"


def load_json_table(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


# ----------------------------
# Biome packs
# ----------------------------

def load_biome_pack(tables_dir: Path) -> Dict[str, Any]:
    return load_json_table(tables_dir / "biomes.json", default={"biomes": []})


def load_extremes(tables_dir: Path) -> Dict[str, Any]:
    return load_json_table(tables_dir / "extremes.json", default={"extremes": []})


def load_calendars(tables_dir: Path) -> Dict[str, Any]:
    return load_json_table(tables_dir / "calendars.json", default={"calendars": []})


def get_biome(biome_pack: Dict[str, Any], biome_id: str) -> Dict[str, Any]:
    for b in biome_pack.get("biomes", []):
        if b.get("id") == biome_id:
            return b
    # Fallback: first biome
    biomes = biome_pack.get("biomes", [])
    return biomes[0] if biomes else {
        "id": "temperate_forest",
        "name": "Temperate Forest",
        "tags": ["Temperate", "Forest"],
        "temp_c": {"winter": 0, "spring": 8, "summer": 20, "autumn": 10},
        "temp_variance": 6,
        "precip_chance": {"winter": 0.35, "spring": 0.45, "summer": 0.35, "autumn": 0.45},
        "storm_chance": {"winter": 0.06, "spring": 0.10, "summer": 0.12, "autumn": 0.08},
        "fog_chance": {"winter": 0.10, "spring": 0.08, "summer": 0.05, "autumn": 0.12},
        "wind_avg_kph": 12,
        "wind_gust_chance": 0.18,
        "special": {}
    }


def get_calendar(cal_table: Dict[str, Any], calendar_id: str) -> CalendarConfig:
    for c in cal_table.get("calendars", []):
        if c.get("id") == calendar_id:
            return CalendarConfig(
                calendar_id=c["id"],
                name=c.get("name", c["id"]),
                months=list(c["months"]),
                days_in_month=list(c["days_in_month"]),
                weekday_names=list(c.get("weekday_names", ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]))
            )
    # Default 12x30 fantasy
    return CalendarConfig(
        calendar_id="fantasy_360",
        name="Fantasy 360",
        months=[f"Month {i+1}" for i in range(12)],
        days_in_month=[30]*12,
        weekday_names=["Mo","Tu","We","Th","Fr","Sa","Su"]
    )


# ----------------------------
# Weather simulation
# ----------------------------

WEATHER_TYPES = ["Clear", "Cloudy", "Rain", "Storm", "Snow", "Fog", "Hail", "Dust"]
PRECIP_TYPES = ["None", "Rain", "Snow", "Sleet", "Hail", "Ash"]
INTENSITIES = ["None", "Light", "Moderate", "Heavy", "Violent"]

def _choose_weighted(rng: random.Random, items: List[Tuple[Any, float]]) -> Any:
    total = sum(max(0.0, w) for _, w in items)
    if total <= 0:
        return items[0][0]
    x = rng.random() * total
    s = 0.0
    for item, w in items:
        s += max(0.0, w)
        if x <= s:
            return item
    return items[-1][0]


def _intensity_from_amount(rng: random.Random, amount: float) -> str:
    # amount is 0..1
    if amount <= 0.05:
        return "Light"
    if amount <= 0.20:
        return "Moderate"
    if amount <= 0.45:
        return "Heavy"
    # Rarely violent
    return "Violent" if rng.random() < 0.35 else "Heavy"


def _visibility(cond: str, wind_kph: float, intensity: str) -> str:
    if cond in ("Fog",):
        return "Very Poor"
    if cond in ("Storm", "Snow", "Hail"):
        return "Poor" if intensity in ("Heavy", "Violent") else "Fair"
    if wind_kph >= 35:
        return "Fair"
    return "Good"


def _daylight_hours(day_of_year: int, days_per_year: int, latitude: float, hemisphere: str) -> float:
    # Approximate daylight curve; clamped for sanity.
    # Not astronomically perfect, but coherent and nice for play.
    lat = _clamp(abs(latitude), 0.0, 66.0)
    seasonal = _seasonal_t(day_of_year, days_per_year, hemisphere)  # -1..1
    # amplitude increases with latitude
    amp = 3.5 + (lat / 66.0) * 4.5  # 3.5..8.0 hours swing
    base = 12.0
    return _clamp(base + amp * seasonal, 6.0, 18.0)


def _temp_for_day(biome: Dict[str, Any], day_of_year: int, cal: CalendarConfig, cfg: WeatherConfig, rng: random.Random) -> float:
    # Use seasonal curve to blend between winter and summer, with spring/autumn shaping.
    s = _seasonal_t(day_of_year, cal.days_per_year, cfg.hemisphere)  # -1..1
    # Determine seasonal key
    # Weighting: winter(-1), summer(+1), spring/autumn around 0
    t_w = biome["temp_c"].get("winter", 0)
    t_sp = biome["temp_c"].get("spring", 8)
    t_su = biome["temp_c"].get("summer", 20)
    t_au = biome["temp_c"].get("autumn", 10)

    # Two-step blend: pick mid-season based on sign
    if s < 0:
        # winter -> spring
        a = (s + 1.0)  # 0..1
        base = (1-a) * t_w + a * t_sp
    else:
        # autumn -> summer -> autumn, but we want spring to summer; use summer->autumn
        a = s  # 0..1
        base = (1-a) * t_au + a * t_su

    # Latitude and elevation effects
    base -= (abs(cfg.latitude) - 45.0) * 0.08  # colder further from 45
    base -= (cfg.elevation_m / 1000.0) * 6.5   # standard lapse rate

    # Year anomaly
    base += cfg.anomaly * 2.0

    # Daily noise
    var = float(biome.get("temp_variance", 6))
    noise = rng.gauss(0.0, var * 0.35)
    # Front persistence: caller may add additional smoothing; we keep moderate noise.
    return base + noise


def _precip_for_day(biome: Dict[str, Any], day_of_year: int, cal: CalendarConfig, cfg: WeatherConfig, temp_c: float, rng: random.Random) -> Tuple[str, str, float]:
    # Determine season bucket by day position
    frac = day_of_year / max(1, cal.days_per_year)
    if frac < 0.25:
        season = "winter"
    elif frac < 0.50:
        season = "spring"
    elif frac < 0.75:
        season = "summer"
    else:
        season = "autumn"

    base_ch = float(biome.get("precip_chance", {}).get(season, 0.35))
    base_ch = _clamp(base_ch * cfg.wetness, 0.0, 0.98)

    if rng.random() > base_ch:
        return ("None", "None", 0.0)

    # Amount 0..1, biased by biome special precipitation profile
    profile = biome.get("precip_profile", "default")
    if profile == "arid":
        amount = rng.random() ** 2.4
    elif profile == "monsoon":
        amount = 0.4 + 0.6 * (rng.random() ** 0.7)
    elif profile == "maritime":
        amount = 0.2 + 0.8 * (rng.random() ** 1.0)
    else:
        amount = rng.random() ** 1.3

    intensity = _intensity_from_amount(rng, amount)

    # Determine precip type based on temp and biome special
    if biome.get("special", {}).get("ashfall", False) and rng.random() < 0.06:
        return ("Ash", intensity, amount)

    if temp_c <= -1.0:
        return ("Snow", intensity, amount)
    if temp_c <= 2.0 and rng.random() < 0.25:
        return ("Sleet", intensity, amount)
    return ("Rain", intensity, amount)


def _condition_for_day(biome: Dict[str, Any], cfg: WeatherConfig, temp_c: float, precip_type: str, precip_intensity: str, rng: random.Random, day_of_year: int, cal: CalendarConfig) -> str:
    # Fog first
    frac = day_of_year / max(1, cal.days_per_year)
    if frac < 0.25:
        season = "winter"
    elif frac < 0.50:
        season = "spring"
    elif frac < 0.75:
        season = "summer"
    else:
        season = "autumn"

    fog_ch = float(biome.get("fog_chance", {}).get(season, biome.get("fog_chance", 0.08)))
    if rng.random() < fog_ch and precip_type == "None":
        return "Fog"

    # Storminess depends on precip and storm chance
    storm_base = float(biome.get("storm_chance", {}).get(season, biome.get("storm_chance", 0.08)))
    storm_base = _clamp(storm_base * cfg.storminess, 0.0, 0.95)

    if precip_type != "None" and rng.random() < storm_base:
        # Snowstorm vs thunderstorm depending on temp
        return "Snow" if precip_type in ("Snow", "Sleet") else "Storm"

    if precip_type in ("Rain", "Sleet", "Ash"):
        return "Rain" if precip_type != "Ash" else "Cloudy"
    if precip_type == "Snow":
        return "Snow"

    # Cloudiness depends on humidity (wetness) and biome
    base_cloud = 0.25 + 0.20 * (cfg.wetness - 1.0)
    base_cloud += 0.10 * (storm_base - 0.08)
    base_cloud = _clamp(base_cloud, 0.05, 0.85)
    return "Cloudy" if rng.random() < base_cloud else "Clear"


def _wind_for_day(biome: Dict[str, Any], cond: str, precip_intensity: str, cfg: WeatherConfig, rng: random.Random) -> Tuple[int, bool, str]:
    avg = float(biome.get("wind_avg_kph", 12))
    gust_ch = float(biome.get("wind_gust_chance", 0.18))

    # Condition affects wind
    if cond in ("Storm", "Snow"):
        avg *= 1.6
        gust_ch *= 1.4
    if precip_intensity in ("Heavy", "Violent"):
        avg *= 1.2

    speed = max(0, int(rng.gauss(avg, avg * 0.35)))
    gusts = rng.random() < _clamp(gust_ch, 0.0, 0.95)

    # Simple direction for flavor
    dirs = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    direction = dirs[int(rng.random() * len(dirs)) % len(dirs)]
    return speed, gusts, direction


def _tags_for_day(cond: str, precip_type: str, precip_intensity: str, wind_kph: int, temp_c: float, visibility: str) -> List[str]:
    tags: List[str] = ["Weather"]
    tags.append(f"Weather:{cond}")
    if precip_type and precip_type != "None":
        tags.append(f"Weather:{precip_type}")
        tags.append(f"Precip:{precip_intensity}")
    if wind_kph >= 30:
        tags.append("Wind:High")
    if wind_kph >= 45:
        tags.append("Wind:Gale")
    if temp_c <= -10:
        tags.append("Cold:Severe")
    if temp_c >= 32:
        tags.append("Heat:Severe")
    if visibility in ("Poor", "Very Poor"):
        tags.append("Visibility:Poor")
    # Travel heuristics
    travel = "Travel:Normal"
    if cond in ("Storm", "Snow") or precip_intensity in ("Heavy", "Violent") or wind_kph >= 40 or visibility in ("Poor", "Very Poor"):
        travel = "Travel:Hard"
    if cond in ("Snow",) and precip_intensity in ("Heavy", "Violent"):
        travel = "Travel:Very Hard"
    tags.append(travel)
    return tags


def _narrative(cond: str, precip_type: str, precip_intensity: str, wind_kph: int, gusts: bool, temp_c: float, daylight_h: float, biome_name: str, style: str, rng: random.Random) -> str:
    # Style changes diction only. Keep it short, usable at the table.
    hot = temp_c >= 30
    cold = temp_c <= -5
    windy = wind_kph >= 30
    gloomy = cond in ("Cloudy", "Fog", "Rain", "Snow")

    if style == "OSR Minimal":
        parts = []
        parts.append(f"{cond}.")
        if precip_type != "None":
            parts.append(f"{precip_type} ({precip_intensity}).")
        parts.append(f"Wind {wind_kph}kph" + (" gusts." if gusts else "."))
        parts.append(f"Temp {_fmt_temp(temp_c)}.")
        return " ".join(parts)

    if style == "Grimdark":
        openers = [
            "The sky hangs low and mean.",
            "The day arrives like a threat.",
            "Morning crawls in under a bruise-colored ceiling.",
            "The air tastes wrong."
        ]
    elif style == "Pastoral":
        openers = [
            "The day opens gently.",
            "Light spills across the land.",
            "Birdsong and breeze share the morning.",
            "Dawn comes clean and bright."
        ]
    elif style == "Mythic":
        openers = [
            "The heavens turn their great wheel.",
            "Old winds walk the world again.",
            "The season speaks in cloud and flame.",
            "A familiar omen rides the air."
        ]
    else:
        openers = [
            "The day starts quietly.",
            "Morning arrives with a steady feel to it.",
            "The weather settles into a clear pattern.",
            "The air carries the day's promise."
        ]

    opener = rng.choice(openers)

    beats: List[str] = []
    if cond == "Clear":
        beats.append("Skies are mostly clear.")
        if hot:
            beats.append("Heat builds toward afternoon.")
        if cold:
            beats.append("The cold stays sharp even at midday.")
    elif cond == "Cloudy":
        beats.append("A lid of cloud dulls the sun.")
    elif cond == "Fog":
        beats.append("Fog pools low and stubborn, swallowing distance.")
    elif cond == "Rain":
        if precip_intensity in ("Light", "Moderate"):
            beats.append("Rain comes and goes in patient sheets.")
        else:
            beats.append("Rain hammers down hard enough to blur the world.")
    elif cond == "Storm":
        beats.append("Thunder and sudden violence roll through in waves.")
        if precip_intensity in ("Heavy", "Violent"):
            beats.append("Anything loose gets torn free.")
    elif cond == "Snow":
        if precip_intensity in ("Light", "Moderate"):
            beats.append("Snow drifts softly, whitening edges and footprints.")
        else:
            beats.append("Snow drives sideways, erasing trails within minutes.")
    elif cond == "Hail":
        beats.append("Hail rattles like thrown gravel.")
    elif cond == "Dust":
        beats.append("Dust rides the wind in gritty curtains.")

    if precip_type == "Ash":
        beats.append("Fine ash sifts down, coating everything in gray.")

    if windy:
        beats.append(f"A strong {wind_kph} kph wind worries cloaks and canvas.")
    elif wind_kph >= 18:
        beats.append("A steady breeze keeps things moving.")

    beats.append(f"Daylight: {daylight_h:.1f} hours.")

    # Biome flavor
    if style in ("Mythic", "Grimdark") and rng.random() < 0.35:
        beats.append(rng.choice([
            f"In the {biome_name.lower()}, even this feels watched.",
            f"The {biome_name.lower()} carries old moods in its weather.",
            f"The land answers the sky with quiet insistence."
        ]))

    return opener + " " + " ".join(beats)


def _apply_front_smoothing(days: List[Dict[str, Any]], rng: random.Random) -> None:
    """
    Adds coherence by smoothing temperature and condition changes over multi-day stretches.
    This is intentionally lightweight (no heavy meteorology), but removes "whiplash".
    """
    if not days:
        return
    # Temperature smoothing
    for i in range(1, len(days)):
        prev = days[i-1]["temperature_c"]
        cur = days[i]["temperature_c"]
        days[i]["temperature_c"] = 0.65 * cur + 0.35 * prev

    # Condition persistence: occasionally carry condition forward if close
    for i in range(1, len(days)):
        if rng.random() < 0.28:
            if days[i]["precip"]["type"] == "None" and days[i-1]["precip"]["type"] == "None":
                # Persist clear/cloudy/fog
                if days[i-1]["condition"] in ("Clear", "Cloudy", "Fog"):
                    days[i]["condition"] = days[i-1]["condition"]
            else:
                # Persist rain/snow
                if days[i-1]["condition"] in ("Rain", "Snow") and rng.random() < 0.45:
                    days[i]["condition"] = days[i-1]["condition"]


def simulate_year(
    rng: random.Random,
    biome: Dict[str, Any],
    cal: CalendarConfig,
    cfg: WeatherConfig,
    extremes_table: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Returns:
    {
      "calendar": {...},
      "biome": {...},
      "config": {...},
      "days": [ { ... day record ... } ],
      "extreme_events": [ { ... } ],
      "summary": {...}
    }
    """
    days: List[Dict[str, Any]] = []
    # Pre-roll a "year drift" for additional coherence
    drift = rng.gauss(0.0, 0.9) + cfg.anomaly
    drift = _clamp(drift, -2.0, 2.0)

    for d in range(cal.days_per_year):
        day_rng = random.Random(rng.randint(0, 2**31-1))
        temp = _temp_for_day(biome, d, cal, cfg, day_rng) + drift
        precip_type, precip_intensity, precip_amount = _precip_for_day(biome, d, cal, cfg, temp, day_rng)
        cond = _condition_for_day(biome, cfg, temp, precip_type, precip_intensity, day_rng, d, cal)

        wind_kph, gusts, wind_dir = _wind_for_day(biome, cond, precip_intensity, cfg, day_rng)
        vis = _visibility(cond, wind_kph, precip_intensity)
        daylight_h = _daylight_hours(d, cal.days_per_year, cfg.latitude, cfg.hemisphere)

        record = {
            "day_index": d,
            "date": None,  # filled by date mapping helper
            "weekday": None,
            "season_value": _seasonal_t(d, cal.days_per_year, cfg.hemisphere),
            "temperature_c": float(temp),
            "condition": cond,
            "precip": {
                "type": precip_type,
                "intensity": precip_intensity,
                "amount": float(precip_amount),
            },
            "wind": {
                "speed_kph": int(wind_kph),
                "gusts": bool(gusts),
                "direction": str(wind_dir),
            },
            "daylight_hours": float(daylight_h),
            "visibility": str(vis),
            "tags": [],  # filled below
            "notes": "",
            "narrative": "",
        }
        record["tags"] = _tags_for_day(cond, precip_type, precip_intensity, wind_kph, temp, vis)
        if cfg.generate_narrative:
            record["narrative"] = _narrative(cond, precip_type, precip_intensity, wind_kph, gusts, temp, daylight_h, biome.get("name", "Biome"), cfg.narrative_style, day_rng)
        days.append(record)

    # Coherence smoothing
    _apply_front_smoothing(days, rng)

    # Map calendar dates
    _assign_calendar_dates(days, cal)

    # Inject extreme events (rare, multi-day)
    extreme_events = _inject_extremes(days, biome, cal, cfg, rng, extremes_table)

    # Summary
    summary = compute_summary(days, cal)

    return {
        "calendar": {
            "id": cal.calendar_id,
            "name": cal.name,
            "months": cal.months,
            "days_in_month": cal.days_in_month,
            "weekday_names": cal.weekday_names,
        },
        "biome": {
            "id": biome.get("id"),
            "name": biome.get("name"),
            "tags": biome.get("tags", []),
        },
        "config": {
            "biome_id": cfg.biome_id,
            "year_index": cfg.year_index,
            "calendar_id": cfg.calendar_id,
            "hemisphere": cfg.hemisphere,
            "latitude": cfg.latitude,
            "elevation_m": cfg.elevation_m,
            "anomaly": cfg.anomaly,
            "storminess": cfg.storminess,
            "wetness": cfg.wetness,
            "extreme_rate": cfg.extreme_rate,
            "narrative_style": cfg.narrative_style,
            "generate_narrative": cfg.generate_narrative,
        },
        "days": days,
        "extreme_events": extreme_events,
        "summary": summary,
    }


def _assign_calendar_dates(days: List[Dict[str, Any]], cal: CalendarConfig) -> None:
    # date string: "MonthName Day" plus month index for sorting
    weekday_names = cal.weekday_names or ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]
    wd_count = len(weekday_names)
    di = 0
    for mi, (mname, mdays) in enumerate(zip(cal.months, cal.days_in_month)):
        for d in range(1, mdays+1):
            if di >= len(days):
                return
            days[di]["date"] = {"month_index": mi, "month": mname, "day": d}
            days[di]["weekday"] = weekday_names[di % wd_count]
            di += 1


def _inject_extremes(days: List[Dict[str, Any]], biome: Dict[str, Any], cal: CalendarConfig, cfg: WeatherConfig, rng: random.Random, extremes_table: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Injects rare multi-day events. This modifies day records (tags, notes, sometimes condition/precip).
    """
    events: List[Dict[str, Any]] = []
    base_rate = 0.8 * cfg.extreme_rate
    # biome may bias extremes
    bias = biome.get("special", {}).get("extreme_bias", [])
    if isinstance(bias, str):
        bias = [bias]
    # Expected number of extremes per year ~ 0..6
    expected = _clamp(base_rate * (0.8 + rng.random()*0.8), 0.0, 3.5)
    n = 0
    # Poisson-ish
    while rng.random() < expected / 3.5 and n < 6:
        n += 1

    # Build weights
    pool = list(extremes_table.get("extremes", []))
    if not pool:
        return events

    for _ in range(n):
        start = rng.randint(0, max(0, cal.days_per_year - 5))
        # choose event weighted by biome bias + season appropriateness
        weighted: List[Tuple[Dict[str, Any], float]] = []
        for e in pool:
            w = float(e.get("weight", 1.0))
            eid = e.get("id", "")
            if eid in bias:
                w *= 2.0
            # season gating
            season_ok = e.get("season", "any")
            frac = start / max(1, cal.days_per_year)
            season = "winter" if frac < 0.25 else "spring" if frac < 0.5 else "summer" if frac < 0.75 else "autumn"
            if season_ok != "any" and season_ok != season:
                w *= 0.35
            # temperature gating
            if e.get("requires_cold", False):
                if days[start]["temperature_c"] > 2.0:
                    w *= 0.25
            if e.get("requires_hot", False):
                if days[start]["temperature_c"] < 24.0:
                    w *= 0.25
            weighted.append((e, w))

        event_def = _choose_weighted(rng, weighted)
        dur = int(_clamp(rng.randint(event_def.get("min_days", 2), event_def.get("max_days", 6)), 1, 10))
        end = min(cal.days_per_year - 1, start + dur - 1)

        # Apply
        eid = event_def.get("id", "extreme")
        name = event_def.get("name", eid)
        tags = list(event_def.get("tags", []))
        notes = event_def.get("note", "")
        effects = list(event_def.get("effects", []))

        for di in range(start, end+1):
            day = days[di]
            day["tags"].append(f"Extreme:{eid}")
            for t in tags:
                if t not in day["tags"]:
                    day["tags"].append(t)
            if notes:
                day["notes"] = (day.get("notes","") + ("\n" if day.get("notes") else "") + notes).strip()

            # Optional modifications
            mods = event_def.get("mods", {})
            if isinstance(mods, dict):
                if "temp_delta" in mods:
                    day["temperature_c"] = float(day["temperature_c"] + float(mods["temp_delta"]))
                if "force_condition" in mods and mods["force_condition"]:
                    day["condition"] = str(mods["force_condition"])
                if "force_precip_type" in mods and mods["force_precip_type"]:
                    day["precip"]["type"] = str(mods["force_precip_type"])
                    if day["precip"]["intensity"] == "None":
                        day["precip"]["intensity"] = "Moderate"
                if "force_precip_intensity" in mods and mods["force_precip_intensity"]:
                    day["precip"]["intensity"] = str(mods["force_precip_intensity"])
                if "wind_mul" in mods:
                    day["wind"]["speed_kph"] = int(day["wind"]["speed_kph"] * float(mods["wind_mul"]))

        events.append({
            "id": eid,
            "name": name,
            "start_day_index": start,
            "end_day_index": end,
            "duration_days": end - start + 1,
            "effects": effects,
            "tags": tags,
            "note": notes
        })

    # Deduplicate overlaps (keep simple)
    events.sort(key=lambda e: e["start_day_index"])
    cleaned: List[Dict[str, Any]] = []
    last_end = -1
    for e in events:
        if e["start_day_index"] <= last_end:
            continue
        cleaned.append(e)
        last_end = e["end_day_index"]
    return cleaned


def compute_summary(days: List[Dict[str, Any]], cal: CalendarConfig) -> Dict[str, Any]:
    temps = [d["temperature_c"] for d in days]
    precip_days = sum(1 for d in days if d["precip"]["type"] != "None")
    storms = sum(1 for d in days if d["condition"] == "Storm")
    snows = sum(1 for d in days if d["condition"] == "Snow")
    fogs = sum(1 for d in days if d["condition"] == "Fog")
    windy = sum(1 for d in days if d["wind"]["speed_kph"] >= 30)

    month_stats: List[Dict[str, Any]] = []
    idx = 0
    for mi, (mname, mdays) in enumerate(zip(cal.months, cal.days_in_month)):
        subset = days[idx: idx+mdays]
        idx += mdays
        if not subset:
            continue
        mt = [d["temperature_c"] for d in subset]
        month_stats.append({
            "month": mname,
            "avg_temp_c": float(sum(mt)/len(mt)),
            "min_temp_c": float(min(mt)),
            "max_temp_c": float(max(mt)),
            "precip_days": int(sum(1 for d in subset if d["precip"]["type"] != "None")),
            "storm_days": int(sum(1 for d in subset if d["condition"] == "Storm")),
            "snow_days": int(sum(1 for d in subset if d["condition"] == "Snow")),
            "fog_days": int(sum(1 for d in subset if d["condition"] == "Fog")),
        })

    return {
        "days_per_year": cal.days_per_year,
        "avg_temp_c": float(sum(temps)/len(temps)) if temps else 0.0,
        "min_temp_c": float(min(temps)) if temps else 0.0,
        "max_temp_c": float(max(temps)) if temps else 0.0,
        "precip_days": int(precip_days),
        "storm_days": int(storms),
        "snow_days": int(snows),
        "fog_days": int(fogs),
        "windy_days_30kph": int(windy),
        "months": month_stats,
    }
