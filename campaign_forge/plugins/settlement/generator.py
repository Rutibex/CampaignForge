
from __future__ import annotations

from dataclasses import dataclass, asdict, field
from typing import Dict, List, Optional, Tuple
import math
import random
import uuid

# ----------------------------
# Data model
# ----------------------------

@dataclass
class Faction:
    id: str
    name: str
    kind: str               # "Ruling", "Rival", "Criminal", "Religious", "External"
    goal: str
    method: str
    signature: str

@dataclass
class Location:
    id: str
    name: str
    kind: str               # "Inn", "Market", "Temple", ...
    owner: str              # faction id or "independent"
    hook: str
    secret: str

@dataclass
class District:
    id: str
    name: str
    kind: str               # "Market Ward", "Docks", ...
    wealth: str             # "Poor", "Modest", "Wealthy"
    law: str                # "Low", "Medium", "High"
    danger: str             # "Low", "Medium", "High"
    influence: Dict[str, int] = field(default_factory=dict)   # faction_id -> %
    locations: List[Location] = field(default_factory=list)

    # Layout (map space, set post-generation)
    x: float = 0.0
    y: float = 0.0
    r: float = 1.0

@dataclass
class Settlement:
    id: str
    name: str
    settlement_type: str    # Hamlet/Village/Town/City/...
    population_band: str    # Dozens/Hundreds/Thousands
    age: str                # New/Established/Ancient/Rebuilt
    terrain: str            # Plains/Coast/etc
    tags: List[str]
    has_river: bool
    has_walls: bool

    factions: List[Faction] = field(default_factory=list)
    districts: List[District] = field(default_factory=list)
    problems: List[str] = field(default_factory=list)
    rumors_true: List[str] = field(default_factory=list)
    rumors_false: List[str] = field(default_factory=list)
    rumors_half: List[str] = field(default_factory=list)

    # Map meta
    map_width: int = 1200
    map_height: int = 900
    river_path: List[Tuple[float, float]] = field(default_factory=list)
    wall_center: Tuple[float, float] = (600.0, 450.0)
    wall_radius: float = 340.0

# ----------------------------
# Tables (lightweight, local)
# ----------------------------

SETTLEMENT_TYPES = ["Hamlet", "Village", "Town", "City", "Fortress-Town", "Trade Post", "Ruin-Settlement"]
POP_BANDS = ["Dozens", "Hundreds", "Thousands"]
AGES = ["New", "Established", "Ancient", "Rebuilt"]
TERRAINS = ["Plains", "Hills", "Forest", "Coast", "Desert", "Swamp", "Mountains", "Tundra"]

DISTRICT_KINDS = [
    "Market Ward", "Old Town", "Docks", "Temple District", "Crafts Ward",
    "Garrison", "Noble Quarter", "Shanties", "Arcane Quarter", "Ruins/Undercity"
]

LOCATION_KINDS = [
    "Inn/Tavern", "Market", "Shrine/Temple", "Guildhall", "Watch Post",
    "Manor/House", "Warehouse", "Clinic/Herbalist", "Bathhouse", "Curio Shop",
    "Black Market", "Archive/Library", "Arena", "Ferry/Bridge", "Abandoned Building"
]

PROBLEM_SEEDS = [
    "Food shortages after a failed harvest",
    "A succession dispute is splitting the council",
    "A cult has infiltrated the night watch",
    "Trade caravans are vanishing on the road",
    "A strange illness spreads through one ward",
    "A nearby monster lair is growing bold",
    "The river is poisoned upstream",
    "A feud between guilds is turning violent",
    "A protected ruin has been opened illegally",
    "Foreign agents are buying influence quietly",
    "A relic was stolen from the main temple",
    "The garrison is underpaid and resentful",
]

RUMOR_TEMPLATES_TRUE = [
    "Someone is paying silver for old keys and lockplates.",
    "A tunnel from {district} leads under the river.",
    "The {faction} is preparing a move within a week.",
    "A cellar in {district} hides a sealed stair into older stone.",
    "A merchant ledger names a buyer who doesn't exist.",
]
RUMOR_TEMPLATES_FALSE = [
    "The mayor is a shapeshifter (and eats children).",
    "The well water turns you into fishfolk at midnight.",
    "A dragon sleeps beneath the marketplace (you can hear it snore).",
    "Anyone who enters {district} must speak in rhyme or be arrested.",
    "The {faction} has already fled with the treasury.",
]
RUMOR_TEMPLATES_HALF = [
    "The {faction} runs the black market (but not the one you think).",
    "The new shrine in {district} is blessed (by something).",
    "The river is safe to drink (except downstream of {district}).",
    "A ghost guards the old gate (and it's mostly friendly).",
    "A hidden vault exists (but the map is wrong).",
]

FACTION_KINDS = ["Ruling", "Rival", "Criminal", "Religious", "External"]
FACTION_GOALS = [
    "stability at any cost",
    "profit and control of trade",
    "religious dominance",
    "revenge for an old slight",
    "keep a secret buried",
    "expand territory quietly",
    "remove an 'unfit' leader",
    "break the guild monopoly",
]
FACTION_METHODS = [
    "bribes and favors",
    "open intimidation",
    "blackmail and secrets",
    "charity with strings attached",
    "legal maneuvering",
    "propaganda and rumor",
    "violence by proxy",
]
FACTION_SIGNATURES = [
    "a wax-sealed letter with a strange sigil",
    "coins etched with a tiny star",
    "red thread tied to door handles",
    "chalk marks only visible at dawn",
    "lanterns with green glass",
    "a perfume that lingers in empty rooms",
]

NAME_ADJ = ["Bright", "Hollow", "Salt", "Ash", "Green", "Black", "Golden", "Iron", "Frost", "Sable", "White", "Red"]
NAME_NOUN = ["Harbor", "Ford", "Hearth", "Crown", "Gate", "Cross", "Market", "Quay", "Haven", "Hold", "Bridge", "Watch"]

def _pick(rng: random.Random, xs: List[str]) -> str:
    return xs[rng.randrange(len(xs))]

def _pct_split(rng: random.Random, n: int) -> List[int]:
    # produce n positive ints summing to 100
    cuts = sorted([rng.randint(1, 99) for _ in range(n - 1)])
    parts = [cuts[0]] + [cuts[i] - cuts[i - 1] for i in range(1, n - 1)] + [100 - cuts[-1]]
    # avoid tiny 0-ish parts by smoothing
    parts = [max(5, p) for p in parts]
    s = sum(parts)
    parts = [int(round(p * 100 / s)) for p in parts]
    # fix rounding
    diff = 100 - sum(parts)
    parts[0] += diff
    return parts

# ----------------------------
# Generation
# ----------------------------

def generate_settlement(
    rng: random.Random,
    *,
    name: Optional[str] = None,
    settlement_type: str = "Town",
    population_band: str = "Hundreds",
    age: str = "Established",
    terrain: str = "Plains",
    tags: Optional[List[str]] = None,
    district_count: int = 7,
    has_river: bool = True,
    has_walls: bool = True,
) -> Settlement:
    tags = list(tags or [])
    if not name or not name.strip():
        name = f"{_pick(rng, NAME_ADJ)} {_pick(rng, NAME_NOUN)}"

    sid = str(uuid.uuid4())
    s = Settlement(
        id=sid,
        name=name.strip(),
        settlement_type=settlement_type,
        population_band=population_band,
        age=age,
        terrain=terrain,
        tags=tags,
        has_river=has_river,
        has_walls=has_walls,
    )

    # Factions
    s.factions = _generate_factions(rng, s)

    # Districts + locations
    s.districts = _generate_districts(rng, s, district_count=district_count)

    # Problems and rumors
    s.problems = _generate_problems(rng, s)
    s.rumors_true, s.rumors_false, s.rumors_half = _generate_rumors(rng, s)

    # Layout & map meta
    _layout_settlement(rng, s)

    return s

def _generate_factions(rng: random.Random, s: Settlement) -> List[Faction]:
    count = 4 if s.settlement_type in ("Town", "City") else 3
    if s.settlement_type in ("City",):
        count = 5
    kinds = FACTION_KINDS[:]
    rng.shuffle(kinds)
    factions: List[Faction] = []
    for i in range(count):
        kind = kinds[i % len(kinds)]
        fid = f"f{i+1}"
        factions.append(Faction(
            id=fid,
            name=f"{_pick(rng, NAME_ADJ)} {kind}s",
            kind=kind,
            goal=_pick(rng, FACTION_GOALS),
            method=_pick(rng, FACTION_METHODS),
            signature=_pick(rng, FACTION_SIGNATURES),
        ))
    return factions

def _generate_districts(rng: random.Random, s: Settlement, *, district_count: int) -> List[District]:
    # Ensure required districts for context
    kinds = DISTRICT_KINDS[:]
    # Terrain biases
    required = []
    if s.terrain == "Coast":
        required.append("Docks")
    if s.settlement_type in ("Fortress-Town",):
        required.append("Garrison")
    if s.settlement_type in ("City",):
        required.append("Noble Quarter")
    if s.settlement_type in ("Ruin-Settlement",):
        required.append("Ruins/Undercity")

    chosen: List[str] = []
    for r in required:
        if r in kinds and r not in chosen:
            chosen.append(r)

    rng.shuffle(kinds)
    for k in kinds:
        if len(chosen) >= max(3, district_count):
            break
        if k not in chosen:
            chosen.append(k)

    chosen = chosen[:max(3, district_count)]
    districts: List[District] = []
    for i, kind in enumerate(chosen):
        did = f"d{i+1}"
        wealth = rng.choices(["Poor", "Modest", "Wealthy"], weights=[4, 5, 3])[0]
        if kind in ("Noble Quarter",):
            wealth = "Wealthy"
        if kind in ("Shanties", "Ruins/Undercity"):
            wealth = "Poor"

        law = rng.choices(["Low", "Medium", "High"], weights=[4, 5, 3])[0]
        if kind in ("Garrison", "Noble Quarter"):
            law = "High"
        if kind in ("Shanties", "Ruins/Undercity"):
            law = "Low"

        danger = rng.choices(["Low", "Medium", "High"], weights=[3, 5, 4])[0]
        if kind in ("Ruins/Undercity", "Shanties"):
            danger = "High"

        d = District(
            id=did,
            name=_district_name(rng, kind),
            kind=kind,
            wealth=wealth,
            law=law,
            danger=danger,
        )

        d.locations = _generate_locations(rng, s, d)
        d.influence = _generate_influence(rng, s)

        districts.append(d)
    return districts

def _district_name(rng: random.Random, kind: str) -> str:
    # Keep kind in label for clarity, but add a proper noun
    base = _pick(rng, NAME_ADJ) + " " + _pick(rng, ["Ward", "Quarter", "Row", "Hill", "End", "Green", "Gate"])
    return f"{base} ({kind})"

def _generate_locations(rng: random.Random, s: Settlement, d: District) -> List[Location]:
    n = rng.randint(2, 5)
    locs: List[Location] = []
    for i in range(n):
        lk = _pick(rng, LOCATION_KINDS)
        lid = f"{d.id}_l{i+1}"
        owner = rng.choice([f.id for f in s.factions] + ["independent"])
        name = _location_name(rng, lk)
        hook = _make_hook(rng, s, d, lk)
        secret = _make_secret(rng, s, d, lk)
        locs.append(Location(
            id=lid,
            name=name,
            kind=lk,
            owner=owner,
            hook=hook,
            secret=secret,
        ))
    return locs

def _location_name(rng: random.Random, kind: str) -> str:
    a = _pick(rng, NAME_ADJ)
    n = _pick(rng, ["Swan", "Anchor", "Lantern", "Sickle", "Fox", "Cask", "Candle", "Bell", "Mask", "Crown", "Key"])
    suffix = rng.choice(["", "", "", " House", " Hall", " & Sons", " Yard", " Cellar", " Gate"])
    return f"The {a} {n}{suffix}"

def _make_hook(rng: random.Random, s: Settlement, d: District, kind: str) -> str:
    hooks = [
        f"A regular vanished after mentioning a map under {d.kind.lower()}.",
        f"A courier offers coin to deliver a sealed package across {s.name}.",
        f"A fight broke out over a 'harmless' trinket that won't stop humming.",
        f"Someone is bribing staff to track a particular stranger.",
        f"A quiet patron pays for any rumor about hidden doors.",
    ]
    if kind == "Shrine/Temple":
        hooks += [
            "The candles burn with a second, colder flame.",
            "A saint's relic is missing and everyone is pretending it isn't.",
        ]
    if kind == "Black Market":
        hooks += [
            "A seller offers a key that 'opens anything'—but asks for a name in exchange.",
            "A child is auctioning out secrets they've overheard at court.",
        ]
    return rng.choice(hooks)

def _make_secret(rng: random.Random, s: Settlement, d: District, kind: str) -> str:
    secrets = [
        "There is a trapdoor concealed beneath a movable hearthstone.",
        "A ledger is coded; the key is a nursery rhyme.",
        "The owner is under blackmail from a rival faction.",
        "A backroom shrine honors something not meant to be named.",
        "A hidden tunnel connects to a storm drain outside the walls.",
    ]
    if s.has_river:
        secrets.append("A submerged culvert allows passage beneath the river at low water.")
    if kind == "Archive/Library":
        secrets.append("One shelf is a false wall leading to a sealed study.")
    if kind == "Warehouse":
        secrets.append("One crate contains bones wrapped in waxed cloth, addressed to no one.")
    return rng.choice(secrets)

def _generate_influence(rng: random.Random, s: Settlement) -> Dict[str, int]:
    # choose 2-3 factions to influence this district
    fids = [f.id for f in s.factions]
    rng.shuffle(fids)
    k = rng.randint(2, min(3, len(fids)))
    chosen = fids[:k]
    parts = _pct_split(rng, k)
    return {chosen[i]: parts[i] for i in range(k)}

def _generate_problems(rng: random.Random, s: Settlement) -> List[str]:
    n = 2 if s.settlement_type in ("Hamlet", "Village") else 3
    probs = rng.sample(PROBLEM_SEEDS, k=min(n, len(PROBLEM_SEEDS)))
    # Slight terrain flavor
    if s.terrain == "Coast":
        probs.append("Storm damage has crippled the docks and the harbor master is hiding the numbers.")
    if s.terrain == "Swamp":
        probs.append("The fog carries voices; some people follow them into the reeds.")
    if s.settlement_type == "Ruin-Settlement":
        probs.append("The ruins beneath have 'woken up'—doors are appearing where none existed.")
    return probs[:5]

def _render_template(rng: random.Random, tpl: str, *, district: str, faction: str) -> str:
    return tpl.format(district=district, faction=faction)

def _generate_rumors(rng: random.Random, s: Settlement) -> Tuple[List[str], List[str], List[str]]:
    dname = rng.choice(s.districts).kind if s.districts else "Old Town"
    fname = rng.choice(s.factions).name if s.factions else "Council"
    true = [_render_template(rng, rng.choice(RUMOR_TEMPLATES_TRUE), district=dname, faction=fname) for _ in range(4)]
    false = [_render_template(rng, rng.choice(RUMOR_TEMPLATES_FALSE), district=dname, faction=fname) for _ in range(4)]
    half = [_render_template(rng, rng.choice(RUMOR_TEMPLATES_HALF), district=dname, faction=fname) for _ in range(4)]
    return true, false, half

# ----------------------------
# Layout
# ----------------------------

def _layout_settlement(rng: random.Random, s: Settlement) -> None:
    W, H = s.map_width, s.map_height
    cx, cy = W * 0.5, H * 0.5
    s.wall_center = (cx, cy)

    # River path (simple bezier-ish polyline)
    if s.has_river:
        y0 = rng.uniform(H*0.2, H*0.8)
        y1 = rng.uniform(H*0.2, H*0.8)
        s.river_path = [
            (0.0, y0),
            (W*0.33, (y0+y1)/2 + rng.uniform(-80, 80)),
            (W*0.66, (y0+y1)/2 + rng.uniform(-80, 80)),
            (float(W), y1),
        ]
    else:
        s.river_path = []

    # Assign radii by district scale
    base_r = 95.0 if s.settlement_type in ("Hamlet","Village") else 120.0
    if s.settlement_type in ("City",):
        base_r = 140.0

    # Place districts in ring(s)
    n = len(s.districts)
    angles = [2*math.pi * i / max(1, n) for i in range(n)]
    rng.shuffle(angles)

    for i, d in enumerate(s.districts):
        # position bias by kind
        ring = rng.uniform(0.55, 0.95)
        if d.kind in ("Market Ward", "Old Town", "Temple District"):
            ring = rng.uniform(0.15, 0.45)
        if d.kind in ("Noble Quarter", "Garrison"):
            ring = rng.uniform(0.20, 0.55)
        if d.kind in ("Shanties", "Ruins/Undercity"):
            ring = rng.uniform(0.70, 1.05)
        if d.kind == "Docks" and s.terrain == "Coast":
            ring = rng.uniform(0.75, 1.00)

        a = angles[i % len(angles)] + rng.uniform(-0.25, 0.25)
        # If river exists, bias docks towards it
        if d.kind == "Docks" and s.has_river:
            a = rng.choice([math.pi*0.05, math.pi*0.95, math.pi*1.05, math.pi*1.95]) + rng.uniform(-0.2,0.2)

        # Walls radius
        s.wall_radius = min(W, H) * (0.38 if s.has_walls else 0.0)
        max_rad = min(W, H) * 0.45
        rpos = ring * max_rad

        d.x = cx + math.cos(a) * rpos
        d.y = cy + math.sin(a) * rpos
        d.r = base_r + rng.uniform(-25, 35)

    # Relax overlaps with a few iterations
    for _ in range(140):
        moved = False
        for i in range(n):
            for j in range(i+1, n):
                a = s.districts[i]
                b = s.districts[j]
                dx = b.x - a.x
                dy = b.y - a.y
                dist = math.hypot(dx, dy) + 1e-6
                min_dist = (a.r + b.r) * 0.92
                if dist < min_dist:
                    push = (min_dist - dist) * 0.5
                    ux, uy = dx / dist, dy / dist
                    a.x -= ux * push
                    a.y -= uy * push
                    b.x += ux * push
                    b.y += uy * push
                    moved = True
        # keep inside bounds
        for d in s.districts:
            d.x = max(d.r + 20, min(W - d.r - 20, d.x))
            d.y = max(d.r + 20, min(H - d.r - 20, d.y))
        if not moved:
            break

def settlement_to_dict(s: Settlement) -> Dict:
    return asdict(s)

def settlement_from_dict(data: Dict) -> Settlement:
    # Best-effort load (robust to missing keys)
    def _get(k, default=None):
        return data.get(k, default)

    s = Settlement(
        id=_get("id",""),
        name=_get("name",""),
        settlement_type=_get("settlement_type","Town"),
        population_band=_get("population_band","Hundreds"),
        age=_get("age","Established"),
        terrain=_get("terrain","Plains"),
        tags=_get("tags",[]) or [],
        has_river=bool(_get("has_river", True)),
        has_walls=bool(_get("has_walls", True)),
    )
    s.map_width = int(_get("map_width", 1200))
    s.map_height = int(_get("map_height", 900))
    s.river_path = [tuple(x) for x in (_get("river_path", []) or [])]
    s.wall_center = tuple(_get("wall_center", (600.0, 450.0)))
    s.wall_radius = float(_get("wall_radius", 340.0))

    s.factions = [Faction(**f) for f in (_get("factions", []) or [])]

    districts = []
    for d in (_get("districts", []) or []):
        locs = [Location(**l) for l in (d.get("locations", []) or [])]
        dd = District(
            id=d.get("id",""),
            name=d.get("name",""),
            kind=d.get("kind",""),
            wealth=d.get("wealth","Modest"),
            law=d.get("law","Medium"),
            danger=d.get("danger","Medium"),
            influence=d.get("influence", {}) or {},
            locations=locs,
            x=float(d.get("x", 0.0)),
            y=float(d.get("y", 0.0)),
            r=float(d.get("r", 1.0)),
        )
        districts.append(dd)
    s.districts = districts

    s.problems = _get("problems", []) or []
    s.rumors_true = _get("rumors_true", []) or []
    s.rumors_false = _get("rumors_false", []) or []
    s.rumors_half = _get("rumors_half", []) or []
    return s
