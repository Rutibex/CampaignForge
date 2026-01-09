from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional, Tuple
import math
import random
import uuid
import json
from importlib import resources


def _load_table(name: str) -> Any:
    """Load a JSON table bundled with this plugin."""
    try:
        with resources.files(__package__).joinpath(f"tables/{name}").open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        # Fallback: try relative path on disk
        import pathlib
        p = pathlib.Path(__file__).parent / "tables" / name
        with p.open("r", encoding="utf-8") as f:
            return json.load(f)


STAR_TYPES = _load_table("star_types.json")
PLANET_CLASSES = _load_table("planet_classes.json")
BIOSPHERES = _load_table("biospheres.json")
CULTURES = _load_table("cultures.json")
GOVERNMENTS = _load_table("governments.json")
HAZARDS = _load_table("hazards.json")
TRADE_GOODS = _load_table("trade_goods.json")
HOOKS = _load_table("hooks.json")
NAME_SYL = _load_table("name_syllables.json")


@dataclass
class SystemConfig:
    star_count: int = 1
    max_orbits: int = 12
    orbital_realism: str = "semi"          # cinematic|semi|hard
    life_rarity: str = "rare"              # none|rare|common|engineered
    civ_density: str = "sparse"            # empty|sparse|clustered
    include_exotics: bool = True
    include_ruins: bool = True
    include_trade: bool = True
    include_hazards: bool = True


def make_name(rng: random.Random, kind: str) -> str:
    if kind == "star":
        pre = rng.choice(NAME_SYL["star_prefix"])
        suf = rng.choice(NAME_SYL["star_suffix"])
        return pre + suf
    pre = rng.choice(NAME_SYL["planet_prefix"])
    suf = rng.choice(NAME_SYL["planet_suffix"])
    # avoid awkward double spaces
    return (pre + suf).replace("  ", " ").strip()


def pick_star_type(rng: random.Random) -> Dict[str, Any]:
    # Weighted toward G/K/M for playability
    weights = []
    for st in STAR_TYPES:
        code = st.get("code", "")
        w = 1.0
        if code == "G": w = 3.5
        elif code == "K": w = 3.0
        elif code == "M": w = 3.0
        elif code == "F": w = 1.8
        elif code == "A": w = 1.0
        elif code == "WD": w = 0.8
        elif code == "NS": w = 0.2
        weights.append(w)
    return rng.choices(STAR_TYPES, weights=weights, k=1)[0]


def habitable_zone(primary_star: Dict[str, Any]) -> Tuple[float, float]:
    return float(primary_star.get("hz_inner", 0.95)), float(primary_star.get("hz_outer", 1.7))


def _orbit_spacing_factor(rng: random.Random, realism: str) -> float:
    if realism == "cinematic":
        return rng.uniform(1.25, 1.6)
    if realism == "hard":
        return rng.uniform(1.45, 2.05)
    return rng.uniform(1.35, 1.85)


def _planet_class_for_orbit(rng: random.Random, au: float, hz: Tuple[float, float], include_exotics: bool) -> Dict[str, Any]:
    inner, outer = hz
    band = "hz" if inner <= au <= outer else ("inner" if au < inner else "outer")
    candidates = [p for p in PLANET_CLASSES if p.get("band") in (band, "any")]
    if not include_exotics:
        candidates = [p for p in candidates if p.get("key") not in ("ringworld", "dyson")]
    # Bias: gas giants more likely far out, lava more likely near in
    weights = []
    for p in candidates:
        key = p.get("key")
        w = 1.0
        if key == "gas_giant":
            w = 0.3 if band != "outer" else 3.0
        if key == "lava":
            w = 2.0 if band == "inner" else 0.2
        if key == "garden":
            w = 2.0 if band == "hz" else 0.1
        if key == "ocean":
            w = 1.8 if band == "hz" else 0.1
        if key in ("ringworld", "dyson"):
            w = 0.05
        weights.append(w)
    return rng.choices(candidates, weights=weights, k=1)[0]


def _roll_uwp_hex(rng: random.Random, maxv: int) -> int:
    return max(0, min(maxv, int(rng.triangular(0, maxv, maxv/2))))


def make_uwp(rng: random.Random, pclass_key: str, *, has_life: bool, inhabited: bool) -> Dict[str, Any]:
    # Traveller-ish, but tuned for playability.
    size = _roll_uwp_hex(rng, 10)
    atmo = _roll_uwp_hex(rng, 15)
    hydro = _roll_uwp_hex(rng, 10)
    pop = 0
    if inhabited:
        pop = max(1, _roll_uwp_hex(rng, 15))
    gov = _roll_uwp_hex(rng, 15) if inhabited else 0
    law = _roll_uwp_hex(rng, 15) if inhabited else 0
    tech = _roll_uwp_hex(rng, 15) if inhabited else 0

    # Class nudges
    if pclass_key in ("lava", "barren"):
        atmo = min(atmo, 3)
        hydro = 0
    if pclass_key == "ice":
        hydro = min(hydro, 3)
    if pclass_key == "ocean":
        hydro = max(hydro, 8)
    if pclass_key == "garden":
        atmo = max(atmo, 5)
        hydro = max(hydro, 4)
    if pclass_key == "super_earth":
        size = max(size, 8)
    if pclass_key == "tidal":
        law = min(15, law + 1) if inhabited else law

    if has_life and not inhabited:
        # life without population -> keep pop 0
        pop = 0

    # Tech nudges
    if inhabited:
        if pclass_key in ("barren", "ice", "tidal"):
            tech = min(15, tech + 1)
        if pclass_key in ("garden", "ocean"):
            tech = max(tech, 6)

    return {
        "starport": rng.choice(list("XEDCBA")) if inhabited else "-",
        "size": size,
        "atmosphere": atmo,
        "hydro": hydro,
        "population": pop,
        "government": gov,
        "law": law,
        "tech": tech,
    }


def _life_flag(rng: random.Random, cfg: SystemConfig, in_hz: bool, pclass_key: str) -> bool:
    if cfg.life_rarity == "none":
        return False
    if cfg.life_rarity == "engineered":
        # engineered life can appear anywhere but rarely
        return in_hz or rng.random() < 0.05
    # Natural life: mostly in HZ, and avoid lava/barren
    if pclass_key in ("lava", "barren"):
        return False
    base = 0.0
    if cfg.life_rarity == "common":
        base = 0.55
    elif cfg.life_rarity == "rare":
        base = 0.18
    # Out of HZ life (ice oceans etc.)
    if not in_hz:
        base *= 0.20
        if pclass_key in ("ice", "gas_giant"):
            base *= 1.8
    return rng.random() < base


def _inhabited_flag(rng: random.Random, cfg: SystemConfig, has_life: bool, pclass_key: str, au: float) -> bool:
    if cfg.civ_density == "empty":
        return False
    # Inhabited worlds are more likely in HZ or as habitats around gas giants
    base = 0.02 if cfg.civ_density == "sparse" else 0.08
    if has_life:
        base *= 3.0
    if pclass_key in ("garden", "ocean", "swamp", "desert"):
        base *= 2.2
    if pclass_key == "gas_giant":
        base *= 0.3  # the planet itself isn't inhabited; moons are
    if au < 0.25:
        base *= 0.3
    return rng.random() < base


def _pick_biosphere(rng: random.Random, cfg: SystemConfig) -> Dict[str, Any]:
    if cfg.life_rarity == "engineered":
        return next(b for b in BIOSPHERES if b["key"] == "engineered")
    # Weighted
    weights = []
    for b in BIOSPHERES:
        k = b.get("key")
        w = 1.0
        if k == "microbial": w = 2.0
        if k == "complex": w = 1.5
        if k == "exotic": w = 0.4
        if k == "engineered": w = 0.25
        weights.append(w)
    return rng.choices(BIOSPHERES, weights=weights, k=1)[0]


def _pick_culture(rng: random.Random) -> Dict[str, Any]:
    return rng.choice(CULTURES)


def _pick_government(rng: random.Random) -> Dict[str, Any]:
    return rng.choice(GOVERNMENTS)


def _pick_hazards(rng: random.Random, count: int) -> List[Dict[str, Any]]:
    pool = list(HAZARDS)
    rng.shuffle(pool)
    return pool[:max(0, min(count, len(pool)))]



def _pick_hooks(rng: random.Random, count: int) -> List[str]:
    pool = [h.get("text","") for h in (HOOKS or []) if h.get("text")]
    rng.shuffle(pool)
    return pool[:max(0, min(count, len(pool)))]


def _pick_trade_goods(rng: random.Random, count: int) -> List[Dict[str, Any]]:
    pool = list(TRADE_GOODS)
    rng.shuffle(pool)
    return pool[:max(0, min(count, len(pool)))]


def _make_body_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


def generate_system(rng: random.Random, cfg: SystemConfig) -> Dict[str, Any]:
    stars: List[Dict[str, Any]] = []
    for i in range(max(1, cfg.star_count)):
        st = pick_star_type(rng)
        stars.append({
            "id": _make_body_id("star"),
            "name": make_name(rng, "star") + ("" if i == 0 else f"-{i+1}"),
            "type": st,
            "role": "primary" if i == 0 else "companion",
        })
    primary = stars[0]["type"]
    hz = habitable_zone(primary)

    # Orbital lanes: rough log spacing
    orbits: List[Dict[str, Any]] = []
    au = rng.uniform(0.18, 0.45)
    for idx in range(cfg.max_orbits):
        au *= _orbit_spacing_factor(rng, cfg.orbital_realism)
        if au > 70 and cfg.orbital_realism != "cinematic":
            break
        pclass = _planet_class_for_orbit(rng, au, hz, cfg.include_exotics)
        in_hz = hz[0] <= au <= hz[1]
        has_life = _life_flag(rng, cfg, in_hz, pclass["key"])
        inhabited = _inhabited_flag(rng, cfg, has_life, pclass["key"], au)

        planet = {
            "id": _make_body_id("planet"),
            "kind": "planet",
            "name": make_name(rng, "planet"),
            "class": pclass,
            "orbit_index": idx + 1,
            "au": round(au, 3),
            "in_hz": bool(in_hz),
            "has_life": bool(has_life),
            "inhabited": bool(inhabited),
            "uwp": make_uwp(rng, pclass["key"], has_life=has_life, inhabited=inhabited),
            "biosphere": _pick_biosphere(rng, cfg) if has_life else None,
            "culture": _pick_culture(rng) if inhabited else None,
            "government": _pick_government(rng) if inhabited else None,
            "hazards": _pick_hazards(rng, rng.randint(0, 2)) if cfg.include_hazards else [],
            "trade": _pick_trade_goods(rng, rng.randint(1, 3)) if (cfg.include_trade and inhabited) else [],
            "notes": [],
            "moons": [],
        }

        # Moons
        moon_count = 0
        if pclass["key"] == "gas_giant":
            moon_count = rng.randint(4, 14)
        else:
            moon_count = rng.choices([0, 1, 2, 3, 4], weights=[3, 3, 2, 1, 0.4], k=1)[0]
            if pclass["key"] in ("super_earth", "ocean", "garden"):
                moon_count = max(moon_count, rng.choices([0,1,2], weights=[1,3,2], k=1)[0])

        for mi in range(moon_count):
            moon_au = planet["au"]  # share orbit for map; moons have their own micro-orbits
            moon_in_hz = in_hz
            # Moons around gas giants can be habitable even outside HZ (tidal heating)
            moon_has_life = _life_flag(rng, cfg, moon_in_hz or (pclass["key"] == "gas_giant" and rng.random() < 0.25), "ice")
            moon_inhabited = _inhabited_flag(rng, cfg, moon_has_life, "ice", moon_au) and rng.random() < 0.65
            moon_pclass = rng.choice([p for p in PLANET_CLASSES if p.get("key") in ("ice", "barren", "desert", "swamp", "ocean", "garden")])
            moon = {
                "id": _make_body_id("moon"),
                "kind": "moon",
                "name": f"{planet['name']} {chr(97+mi).upper()}" if mi < 26 else f"{planet['name']} M{mi+1}",
                "class": moon_pclass,
                "orbit_index": planet["orbit_index"],
                "au": moon_au,
                "in_hz": bool(moon_in_hz),
                "has_life": bool(moon_has_life),
                "inhabited": bool(moon_inhabited),
                "uwp": make_uwp(rng, moon_pclass["key"], has_life=moon_has_life, inhabited=moon_inhabited),
                "biosphere": _pick_biosphere(rng, cfg) if moon_has_life else None,
                "culture": _pick_culture(rng) if moon_inhabited else None,
                "government": _pick_government(rng) if moon_inhabited else None,
                "hazards": _pick_hazards(rng, rng.randint(0, 2)) if cfg.include_hazards else [],
                "trade": _pick_trade_goods(rng, rng.randint(1, 2)) if (cfg.include_trade and moon_inhabited) else [],
                "notes": [],
            }
            planet["moons"].append(moon)

        # Ruins & hooks
        if cfg.include_ruins and (not inhabited) and rng.random() < 0.15:
            planet["notes"].append("Ancient ruins detected: sealed vaults, dead satellites, or impossible geometry.")
        if inhabited and rng.random() < 0.25:
            planet["notes"].append("Current crisis: shortages, politics, cults, or approaching war.")
        if has_life and not inhabited and rng.random() < 0.20:
            planet["notes"].append("Protected biosphere: research embargo, quarantine beacons, or hidden gardens.")
        if rng.random() < 0.35:
            planet["notes"].extend(_pick_hooks(rng, rng.randint(1, 2)))

        orbits.append(planet)

    # System overview: lanes, belts, comets, special features
    belts = []
    if rng.random() < 0.65:
        belts.append({"kind":"asteroid_belt", "name": make_name(rng, "planet") + " Belt", "au": round(rng.uniform(2.0, 6.0), 2)})
    if rng.random() < 0.35:
        belts.append({"kind":"kuiper_belt", "name": make_name(rng, "planet") + " Kuiper", "au": round(rng.uniform(25.0, 55.0), 1)})

    system = {
        "version": 1,
        "id": _make_body_id("system"),
        "name": make_name(rng, "star") + " System",
        "stars": stars,
        "habitable_zone": {"inner": hz[0], "outer": hz[1]},
        "orbits": orbits,
        "belts": belts,
        "routes": [],
        "tags": [],
        "gm_notes": [],
    }


    # Trade lanes / routes (abstract)
    hubs = []
    for b in iter_bodies(system):
        if b.get("inhabited"):
            hubs.append(b)
    if cfg.include_trade and len(hubs) >= 2:
        # Pick a few hubs (largest pops) and connect them
        def pop(b): 
            try: return int((b.get("uwp") or {}).get("population", 0))
            except Exception: return 0
        hubs.sort(key=pop, reverse=True)
        core = hubs[:min(5, len(hubs))]
        # connect core in a loose ring, then add a few spokes
        for i in range(len(core)):
            a = core[i]
            b = core[(i+1) % len(core)]
            system["routes"].append({"from": a["id"], "to": b["id"], "kind": "trade_lane"})
        # spokes
        for b in hubs[len(core):min(len(hubs), len(core)+6)]:
            a = rng.choice(core)
            system["routes"].append({"from": a["id"], "to": b["id"], "kind": "spoke"})


    # System-level hooks
    if cfg.include_hazards and rng.random() < 0.25:
        system["gm_notes"].append("Navigation hazard: intermittent false beacons in the outer system.")
    if cfg.include_exotics and rng.random() < 0.08:
        system["gm_notes"].append("Exotic signature: a non-planetary mass casts a shadow that shouldn't exist.")
    if cfg.include_trade and rng.random() < 0.35:
        system["gm_notes"].append("Trade opportunity: a rare commodity is abundant here — and contested.")

    return system


def iter_bodies(system: Dict[str, Any]) -> List[Dict[str, Any]]:
    bodies: List[Dict[str, Any]] = []
    for p in system.get("orbits", []):
        bodies.append(p)
        for m in p.get("moons", []):
            bodies.append(m)
    return bodies


def summarize_world(body: Dict[str, Any]) -> str:
    cls = body.get("class", {}).get("name", "World")
    uwp = body.get("uwp", {})
    bits = []
    bits.append(f"**{body.get('name','(unnamed)')}** — *{cls}*  ")
    bits.append(f"Orbit: {body.get('au','?')} AU (Index {body.get('orbit_index','?')})  ")
    if body.get("has_life"):
        bio = body.get("biosphere", {}).get("name", "Life")
        bits.append(f"Life: **Yes** ({bio})  ")
    else:
        bits.append("Life: No  ")
    if body.get("inhabited"):
        bits.append("Inhabited: **Yes**  ")
    else:
        bits.append("Inhabited: No  ")
    if uwp:
        bits.append("UWP: " + " ".join([
            f"Starport {uwp.get('starport','-')}",
            f"Sz {uwp.get('size',0)}",
            f"Atm {uwp.get('atmosphere',0)}",
            f"Hyd {uwp.get('hydro',0)}",
            f"Pop {uwp.get('population',0)}",
            f"Gov {uwp.get('government',0)}",
            f"Law {uwp.get('law',0)}",
            f"TL {uwp.get('tech',0)}",
        ]) + "  ")
    for n in body.get("notes", []) or []:
        bits.append(f"- {n}")
    return "\n".join(bits)
