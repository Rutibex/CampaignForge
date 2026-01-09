from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
import json
import math
import random


# --- constants / utilities ---

COINS_PER_LB = 50  # classic D&D-ish assumption


def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def weighted_choice(rng: random.Random, items: List[Tuple[Any, float]]) -> Any:
    total = sum(max(0.0, w) for _, w in items)
    if total <= 0:
        return items[0][0]
    r = rng.random() * total
    acc = 0.0
    for item, w in items:
        w = max(0.0, w)
        acc += w
        if r <= acc:
            return item
    return items[-1][0]


def _load_json_table(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


# --- config / output structures ---

SCALES = [
    ("Pickpocket", "A single creature's pockets"),
    ("Personal Cache", "Small stash: pouch, boot, bedroll"),
    ("Small Lair", "A lone monster's lair"),
    ("Band / Tribe", "A camp, gang, or small tribe"),
    ("Dungeon Cache", "A significant dungeon find"),
    ("Noble Estate", "Manor vault, family holdings"),
    ("Merchant Vault", "Warehouse strongbox / guild vault"),
    ("Temple Treasury", "Offerings, relics, stored wealth"),
    ("City Reserve", "A city treasury / bank reserve"),
    ("National Treasury", "State vaults, tribute, reserves"),
    ("Legendary Hoard", "Epic dragon hoard / god-king trove"),
]

OWNER_TYPES = [
    "Goblin-kind / Humanoids (poor)",
    "Humanoids (military / raiders)",
    "Humanoids (mercantile / wealthy)",
    "Nobility / Court",
    "Temple / Cult",
    "Arcane order / wizard",
    "Undead (lich / tomb)",
    "Giant-kind",
    "Fiend / Extraplanar",
    "Dragon",
    "Ancient Ruins (unknown)",
]

INTENTS = [
    "Daily carry",
    "Emergency reserve",
    "War chest",
    "Tribute / taxes",
    "Display / trophy",
    "Religious offering",
    "Hidden cache",
    "Obsessive accumulation",
    "Smuggling / contraband",
]

AGES = ["Fresh", "Weathered", "Old", "Ancient", "Mythic"]

MAGIC_DENSITIES = ["Mundane", "Low", "Standard", "High", "Mythic"]


@dataclass
class HoardConfig:
    scale: str
    owner_type: str
    intent: str
    age: str
    culture: str = "Local"
    richness: int = 50               # 0..100 (shifts total value within tier)
    danger: int = 50                 # 0..100 (complications, traps, curses)
    magic_density: str = "Standard"  # enum

    include_coins: bool = True
    include_gems: bool = True
    include_art: bool = True
    include_commodities: bool = True
    include_magic_items: bool = True
    include_scrolls: bool = True
    include_relics: bool = True
    include_complications: bool = True

    track_weight: bool = True
    include_liquidation_notes: bool = True


@dataclass
class HoardOutput:
    version: int
    seed: int
    config: Dict[str, Any]
    totals: Dict[str, Any]
    coins: Dict[str, int]
    gems: List[Dict[str, Any]]
    art: List[Dict[str, Any]]
    commodities: List[Dict[str, Any]]
    magic_items: List[Dict[str, Any]]
    scrolls: List[Dict[str, Any]]
    relics: List[Dict[str, Any]]
    containers: List[Dict[str, Any]]
    complications: List[Dict[str, Any]]
    hooks: List[str]


# --- value model (scale-aware) ---

# GP ranges per scale; "richness" slides within the band.
SCALE_VALUE_RANGES_GP: Dict[str, Tuple[int, int]] = {
    "Pickpocket": (1, 20),
    "Personal Cache": (10, 120),
    "Small Lair": (80, 1200),
    "Band / Tribe": (300, 5000),
    "Dungeon Cache": (1200, 25000),
    "Noble Estate": (6000, 90000),
    "Merchant Vault": (8000, 140000),
    "Temple Treasury": (10000, 220000),
    "City Reserve": (60000, 900000),
    "National Treasury": (400000, 10000000),
    "Legendary Hoard": (800000, 40000000),
}


def _scale_total_gp(cfg: HoardConfig, rng: random.Random) -> int:
    lo, hi = SCALE_VALUE_RANGES_GP.get(cfg.scale, (100, 1000))
    # richness shifts toward hi; also add a small random factor
    t = clamp(cfg.richness / 100.0, 0.0, 1.0)
    base = lo + (hi - lo) * t
    # random within ±15% (keeps determinism while adding texture)
    jitter = 1.0 + (rng.random() * 0.30 - 0.15)
    gp = int(max(1, base * jitter))
    return gp


# --- composition model ---

def _base_composition(cfg: HoardConfig) -> Dict[str, float]:
    """
    Returns target fractions (sum ~ 1.0) for value allocation.
    These are *value* shares, not item counts.
    """
    # baseline: coins dominate at small scales, valuables dominate later
    scale = cfg.scale
    if scale in ("Pickpocket", "Personal Cache"):
        comp = dict(coins=0.85, gems=0.10, art=0.00, commodities=0.05, magic=0.00, scrolls=0.00, relics=0.00)
    elif scale in ("Small Lair", "Band / Tribe"):
        comp = dict(coins=0.65, gems=0.14, art=0.06, commodities=0.10, magic=0.03, scrolls=0.01, relics=0.01)
    elif scale in ("Dungeon Cache",):
        comp = dict(coins=0.52, gems=0.16, art=0.10, commodities=0.10, magic=0.07, scrolls=0.03, relics=0.02)
    elif scale in ("Noble Estate", "Merchant Vault", "Temple Treasury"):
        comp = dict(coins=0.38, gems=0.20, art=0.18, commodities=0.10, magic=0.08, scrolls=0.03, relics=0.03)
    elif scale in ("City Reserve", "National Treasury"):
        comp = dict(coins=0.55, gems=0.12, art=0.10, commodities=0.18, magic=0.03, scrolls=0.01, relics=0.01)
    else:  # Legendary Hoard
        comp = dict(coins=0.42, gems=0.22, art=0.16, commodities=0.07, magic=0.08, scrolls=0.03, relics=0.02)

    owner = cfg.owner_type.lower()
    intent = cfg.intent.lower()
    # nudge based on owner type
    if "dragon" in owner:
        comp["gems"] += 0.08
        comp["art"] += 0.05
        comp["coins"] -= 0.10
    if "temple" in owner or "cult" in owner:
        comp["relics"] += 0.03
        comp["art"] += 0.03
        comp["coins"] -= 0.04
    if "mercantile" in owner or "merchant" in owner:
        comp["commodities"] += 0.10
        comp["coins"] += 0.05
        comp["art"] -= 0.08
    if "undead" in owner or "tomb" in owner:
        comp["art"] += 0.06
        comp["coins"] -= 0.03
        comp["relics"] += 0.02
    if "arcane" in owner or "wizard" in owner:
        comp["magic"] += 0.06
        comp["scrolls"] += 0.03
        comp["coins"] -= 0.05

    # nudge based on intent
    if "display" in intent or "trophy" in intent:
        comp["art"] += 0.08
        comp["gems"] += 0.03
        comp["coins"] -= 0.07
    if "war" in intent:
        comp["coins"] += 0.10
        comp["commodities"] += 0.05
        comp["art"] -= 0.08
    if "tribute" in intent or "tax" in intent:
        comp["coins"] += 0.12
        comp["commodities"] += 0.04
        comp["magic"] -= 0.03
        comp["art"] -= 0.03
    if "smuggling" in intent:
        comp["gems"] += 0.08
        comp["coins"] -= 0.06
        comp["commodities"] += 0.02

    # magic density influences magic/scroll share (value)
    md = cfg.magic_density
    md_mult = {"Mundane": 0.25, "Low": 0.6, "Standard": 1.0, "High": 1.6, "Mythic": 2.2}.get(md, 1.0)
    comp["magic"] *= md_mult
    comp["scrolls"] *= md_mult

    # renormalize
    total = sum(max(0.0, v) for v in comp.values())
    if total <= 0:
        return dict(coins=1.0)
    for k in list(comp.keys()):
        comp[k] = max(0.0, comp[k]) / total
    return comp


# --- generators for each category ---

def _allocate_value(gp_total: int, comp: Dict[str, float]) -> Dict[str, int]:
    # integer allocation with rounding fix
    keys = list(comp.keys())
    raw = {k: gp_total * comp[k] for k in keys}
    alloc = {k: int(math.floor(raw[k])) for k in keys}
    diff = gp_total - sum(alloc.values())
    # distribute remaining gp by largest fractional parts
    fracs = sorted(((k, raw[k] - alloc[k]) for k in keys), key=lambda x: x[1], reverse=True)
    for i in range(max(0, diff)):
        alloc[fracs[i % len(fracs)][0]] += 1
    return alloc


def _gen_coins(rng: random.Random, gp_value: int, cfg: HoardConfig, tables: Dict[str, Any]) -> Dict[str, int]:
    """
    Convert a 'gp_value' budget into coin piles across CP/SP/EP/GP/PP with texture.
    Uses simple exchange rates: 10cp=1sp, 5sp=1ep, 2ep=1gp, 10gp=1pp.
    """
    # choose coin mix weights by owner and age
    w = {"cp": 0.10, "sp": 0.30, "ep": 0.08, "gp": 0.45, "pp": 0.07}
    owner = cfg.owner_type.lower()
    age = cfg.age.lower()
    if "goblin" in owner or "poor" in owner:
        w["cp"] += 0.15; w["sp"] += 0.10; w["gp"] -= 0.18; w["pp"] = max(0.01, w["pp"] - 0.04)
    if "national" in cfg.scale.lower() or "city" in cfg.scale.lower():
        w["gp"] += 0.10; w["pp"] += 0.06; w["cp"] -= 0.06
    if "ancient" in age or "mythic" in age:
        w["ep"] += 0.10; w["gp"] -= 0.06

    # normalize
    tot = sum(max(0.0, x) for x in w.values())
    for k in w:
        w[k] = max(0.0, w[k]) / tot

    # allocate into denominations by repeatedly selecting a denom and paying some chunk
    remaining_gp = gp_value
    coins = {"cp": 0, "sp": 0, "ep": 0, "gp": 0, "pp": 0}

    # conversion values in gp
    denom_gp = {"cp": 0.01, "sp": 0.1, "ep": 0.5, "gp": 1.0, "pp": 10.0}
    denoms = list(denom_gp.keys())

    # avoid too many loops on massive budgets: do chunking
    for _ in range(5000):
        if remaining_gp <= 0.01:
            break
        d = weighted_choice(rng, [(k, w[k]) for k in denoms])
        v = denom_gp[d]
        # choose chunk size (more chunking for large budgets)
        max_chunk_gp = max(v, remaining_gp * (0.25 if remaining_gp < 5000 else 0.05))
        chunk_gp = min(remaining_gp, max(v, rng.random() * max_chunk_gp))
        n = int(chunk_gp / v)
        if n <= 0:
            n = 1
        coins[d] += n
        remaining_gp -= n * v
        if remaining_gp < 0:
            remaining_gp = 0

    # add coin texture: foreign / debased etc (kept as notes in hooks)
    return {k: int(v) for k, v in coins.items() if v > 0}


def _pick_many_with_budget(rng: random.Random, table: List[Dict[str, Any]], budget_gp: int, min_items: int, max_items: int) -> List[Dict[str, Any]]:
    if budget_gp <= 0 or not table:
        return []
    count = clamp(rng.randint(min_items, max_items), 0, 999999)
    # allow count to scale with budget somewhat
    if budget_gp > 20000:
        count = int(count * clamp(1.0 + math.log10(budget_gp / 20000) * 0.6, 1.0, 4.0))
    out: List[Dict[str, Any]] = []
    remaining = budget_gp
    for _ in range(count):
        if remaining <= 0:
            break
        # bias to items below remaining, but allow overshoot a bit (special pieces)
        candidates = [x for x in table if int(x.get("gp", 0)) <= max(remaining * 1.15, 50)]
        if not candidates:
            candidates = table
        item = rng.choice(candidates)
        gp = int(item.get("gp", 0))
        out.append(dict(item))
        remaining -= gp
        # occasionally stop early
        if remaining < 0 or rng.random() < 0.08:
            break
    return out


def _gen_gems(rng: random.Random, budget_gp: int, tables: Dict[str, Any]) -> List[Dict[str, Any]]:
    gems = tables.get("gems", [])
    return _pick_many_with_budget(rng, gems, budget_gp, min_items=1, max_items=8)


def _gen_art(rng: random.Random, budget_gp: int, tables: Dict[str, Any]) -> List[Dict[str, Any]]:
    art = tables.get("art", [])
    return _pick_many_with_budget(rng, art, budget_gp, min_items=1, max_items=6)


def _gen_commodities(rng: random.Random, budget_gp: int, cfg: HoardConfig, tables: Dict[str, Any]) -> List[Dict[str, Any]]:
    comm = tables.get("commodities", [])
    picked = _pick_many_with_budget(rng, comm, budget_gp, min_items=1, max_items=5)
    # add quantity + bulk to commodities
    out = []
    for c in picked:
        unit = c.get("unit", "crate")
        unit_gp = int(c.get("gp", 0))
        # quantity scales with budget
        q = rng.randint(1, 6)
        if budget_gp > 20000:
            q = rng.randint(2, 12)
        if budget_gp > 200000:
            q = rng.randint(6, 40)
        out.append({**c, "qty": q, "unit": unit, "total_gp": unit_gp * q})
    return out


def _magic_counts(scale: str, magic_density: str, rng: random.Random) -> Tuple[int, int]:
    """
    Returns (minor_count, major_count) targets.
    """
    base_minor = {
        "Pickpocket": (0, 0),
        "Personal Cache": (0, 1),
        "Small Lair": (0, 2),
        "Band / Tribe": (1, 3),
        "Dungeon Cache": (2, 5),
        "Noble Estate": (1, 4),
        "Merchant Vault": (0, 2),
        "Temple Treasury": (2, 6),
        "City Reserve": (1, 4),
        "National Treasury": (1, 5),
        "Legendary Hoard": (3, 9),
    }.get(scale, (1, 3))
    base_major = {
        "Pickpocket": (0, 0),
        "Personal Cache": (0, 0),
        "Small Lair": (0, 1),
        "Band / Tribe": (0, 1),
        "Dungeon Cache": (0, 2),
        "Noble Estate": (0, 2),
        "Merchant Vault": (0, 1),
        "Temple Treasury": (0, 2),
        "City Reserve": (0, 2),
        "National Treasury": (0, 3),
        "Legendary Hoard": (1, 4),
    }.get(scale, (0, 1))

    mult = {"Mundane": 0.0, "Low": 0.5, "Standard": 1.0, "High": 1.6, "Mythic": 2.4}.get(magic_density, 1.0)
    mi = int(rng.randint(*base_minor) * mult)
    mj = int(rng.randint(*base_major) * mult)
    return mi, mj


def _gen_magic_items(rng: random.Random, budget_gp: int, cfg: HoardConfig, tables: Dict[str, Any]) -> List[Dict[str, Any]]:
    minor_tbl = tables.get("magic_minor", [])
    major_tbl = tables.get("magic_major", [])
    artifacts_tbl = tables.get("magic_artifacts", [])

    minor_n, major_n = _magic_counts(cfg.scale, cfg.magic_density, rng)
    out: List[Dict[str, Any]] = []

    # choose items; budget for magic is indicative, not strict
    for _ in range(minor_n):
        if not minor_tbl:
            break
        out.append(dict(rng.choice(minor_tbl)))
    for _ in range(major_n):
        if not major_tbl:
            break
        out.append(dict(rng.choice(major_tbl)))

    # artifact chance at high scales/density
    if cfg.scale in ("National Treasury", "Legendary Hoard") and cfg.magic_density in ("High", "Mythic") and artifacts_tbl:
        if rng.random() < (0.22 if cfg.scale == "National Treasury" else 0.45):
            out.append(dict(rng.choice(artifacts_tbl)))

    # give each magic item a small provenance tag
    for it in out:
        it.setdefault("tags", [])
        if "tags" in it and isinstance(it["tags"], list):
            if rng.random() < 0.45:
                it["tags"].append("Heirloom")
            if rng.random() < 0.20:
                it["tags"].append("Cursed?")
            if rng.random() < 0.25:
                it["tags"].append("Signature")
    return out


def _gen_scrolls(rng: random.Random, budget_gp: int, cfg: HoardConfig, tables: Dict[str, Any]) -> List[Dict[str, Any]]:
    scrolls_tbl = tables.get("scrolls", [])
    if not scrolls_tbl:
        return []
    # count driven by budget and density
    mult = {"Mundane": 0.0, "Low": 0.6, "Standard": 1.0, "High": 1.5, "Mythic": 2.2}.get(cfg.magic_density, 1.0)
    base = 0
    if cfg.scale in ("Dungeon Cache", "Temple Treasury"):
        base = rng.randint(0, 3)
    elif cfg.scale in ("City Reserve", "National Treasury"):
        base = rng.randint(0, 4)
    elif cfg.scale == "Legendary Hoard":
        base = rng.randint(1, 6)
    else:
        base = rng.randint(0, 2)
    n = int(base * mult)
    out = [dict(rng.choice(scrolls_tbl)) for _ in range(n)]
    return out


def _gen_relics(rng: random.Random, budget_gp: int, cfg: HoardConfig, tables: Dict[str, Any]) -> List[Dict[str, Any]]:
    relics_tbl = tables.get("relics", [])
    if not relics_tbl:
        return []
    # relic count is tiny
    n = 0
    if cfg.scale in ("Temple Treasury", "National Treasury", "Legendary Hoard"):
        n = rng.randint(0, 2)
    elif cfg.scale in ("Dungeon Cache", "Noble Estate"):
        n = rng.randint(0, 1)
    out = [dict(rng.choice(relics_tbl)) for _ in range(n)]
    return out


def _gen_containers(rng: random.Random, cfg: HoardConfig, tables: Dict[str, Any]) -> List[Dict[str, Any]]:
    cont_tbl = tables.get("containers", [])
    if not cont_tbl:
        return []
    # number based on scale (more storage for bigger hoards)
    n = {"Pickpocket": 1, "Personal Cache": 1, "Small Lair": 2, "Band / Tribe": 2, "Dungeon Cache": 3,
         "Noble Estate": 3, "Merchant Vault": 4, "Temple Treasury": 4, "City Reserve": 6, "National Treasury": 8, "Legendary Hoard": 10}.get(cfg.scale, 3)
    n = int(clamp(n + rng.randint(-1, 2), 1, 20))
    out = [dict(rng.choice(cont_tbl)) for _ in range(n)]
    return out


def _gen_complications(rng: random.Random, cfg: HoardConfig, tables: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[str]]:
    comp_tbl = tables.get("complications", [])
    hooks_tbl = tables.get("hooks", [])
    dangers_tbl = tables.get("dangers", [])
    if not comp_tbl:
        return [], []
    # scale with danger + scale tier
    base = 0
    if cfg.scale in ("Pickpocket", "Personal Cache"):
        base = 0 if cfg.danger < 60 else 1
    elif cfg.scale in ("Small Lair", "Band / Tribe"):
        base = 1
    elif cfg.scale in ("Dungeon Cache", "Noble Estate"):
        base = 2
    elif cfg.scale in ("Merchant Vault", "Temple Treasury", "City Reserve"):
        base = 2 + (1 if cfg.danger > 60 else 0)
    else:
        base = 3 + (1 if cfg.danger > 50 else 0)

    n = int(clamp(base + int(cfg.danger / 40), 0, 8))
    complications = [dict(rng.choice(comp_tbl)) for _ in range(n)]

    # plus a few hooks and dangers
    hooks: List[str] = []
    for _ in range(int(clamp(1 + int(cfg.danger / 50), 1, 4))):
        if hooks_tbl:
            hooks.append(str(rng.choice(hooks_tbl)))
    if cfg.danger > 40 and dangers_tbl:
        for _ in range(int(clamp(int(cfg.danger / 50), 0, 3))):
            hooks.append("DANGER: " + str(rng.choice(dangers_tbl)))
    return complications, hooks


# --- tables loader ---

def load_tables(base_dir: Path) -> Dict[str, Any]:
    """
    base_dir points at this plugin package directory.
    """
    tdir = base_dir / "tables"
    return {
        "gems": _load_json_table(tdir / "gems.json", []),
        "art": _load_json_table(tdir / "art.json", []),
        "commodities": _load_json_table(tdir / "commodities.json", []),
        "magic_minor": _load_json_table(tdir / "magic_minor.json", []),
        "magic_major": _load_json_table(tdir / "magic_major.json", []),
        "magic_artifacts": _load_json_table(tdir / "magic_artifacts.json", []),
        "scrolls": _load_json_table(tdir / "scrolls.json", []),
        "relics": _load_json_table(tdir / "relics.json", []),
        "containers": _load_json_table(tdir / "containers.json", []),
        "complications": _load_json_table(tdir / "complications.json", []),
        "hooks": _load_json_table(tdir / "hooks.json", []),
        "dangers": _load_json_table(tdir / "dangers.json", []),
    }


# --- orchestrator ---

def generate_hoard(cfg: HoardConfig, *, rng: random.Random, tables: Dict[str, Any], seed: int) -> HoardOutput:
    gp_total = _scale_total_gp(cfg, rng)
    comp = _base_composition(cfg)
    alloc = _allocate_value(gp_total, comp)

    # generate categories
    coins = _gen_coins(rng, alloc.get("coins", 0), cfg, tables) if cfg.include_coins else {}
    gems = _gen_gems(rng, alloc.get("gems", 0), tables) if cfg.include_gems else []
    art = _gen_art(rng, alloc.get("art", 0), tables) if cfg.include_art else []
    commodities = _gen_commodities(rng, alloc.get("commodities", 0), cfg, tables) if cfg.include_commodities else []
    magic_items = _gen_magic_items(rng, alloc.get("magic", 0), cfg, tables) if cfg.include_magic_items else []
    scrolls = _gen_scrolls(rng, alloc.get("scrolls", 0), cfg, tables) if cfg.include_scrolls else []
    relics = _gen_relics(rng, alloc.get("relics", 0), cfg, tables) if cfg.include_relics else []
    containers = _gen_containers(rng, cfg, tables)

    complications, hooks = ([], [])
    if cfg.include_complications:
        complications, hooks = _gen_complications(rng, cfg, tables)

    # totals
    coin_gp = int(round(coins.get("cp", 0) * 0.01 + coins.get("sp", 0) * 0.1 + coins.get("ep", 0) * 0.5 + coins.get("gp", 0) * 1.0 + coins.get("pp", 0) * 10.0))
    gems_gp = sum(int(x.get("gp", 0)) for x in gems)
    art_gp = sum(int(x.get("gp", 0)) for x in art)
    comm_gp = sum(int(x.get("total_gp", x.get("gp", 0))) for x in commodities)
    magic_gp = sum(int(x.get("gp_est", 0)) for x in magic_items)
    scrolls_gp = sum(int(x.get("gp_est", 0)) for x in scrolls)
    relics_gp = sum(int(x.get("gp_est", 0)) for x in relics)

    total_gp_est = coin_gp + gems_gp + art_gp + comm_gp + magic_gp + scrolls_gp + relics_gp

    # weight estimate
    coin_count = sum(int(v) for v in coins.values())
    coin_lbs = coin_count / COINS_PER_LB
    bulk_lbs = sum(float(x.get("bulk_lbs", 5)) * float(x.get("qty", 1)) for x in commodities)
    art_lbs = sum(float(x.get("bulk_lbs", 2)) for x in art)
    gems_lbs = sum(float(x.get("bulk_lbs", 0.1)) for x in gems)
    weight_lbs = coin_lbs + bulk_lbs + art_lbs + gems_lbs

    totals = {
        "gp_target": gp_total,
        "gp_estimated": total_gp_est,
        "coins_gp": coin_gp,
        "gems_gp": gems_gp,
        "art_gp": art_gp,
        "commodities_gp": comm_gp,
        "magic_gp_est": magic_gp,
        "scrolls_gp_est": scrolls_gp,
        "relics_gp_est": relics_gp,
        "coin_count": coin_count,
        "weight_lbs_est": round(weight_lbs, 2),
    }

    return HoardOutput(
        version=1,
        seed=seed,
        config=asdict(cfg),
        totals=totals,
        coins=coins,
        gems=gems,
        art=art,
        commodities=commodities,
        magic_items=magic_items,
        scrolls=scrolls,
        relics=relics,
        containers=containers,
        complications=complications,
        hooks=hooks,
    )
