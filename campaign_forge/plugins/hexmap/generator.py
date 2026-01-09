from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional, Any
import json
import random
import re
from pathlib import Path

Coord = Tuple[int, int]  # (q, r)


@dataclass
class HexCell:
    q: int
    r: int
    terrain: str
    poi: Optional[str] = None
    settlement: Optional[Dict[str, Any]] = None


@dataclass
class ThemePack:
    name: str
    terrain_weights: Dict[str, float]
    poi_list: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "terrain_weights": self.terrain_weights,
            "poi_list": self.poi_list,
        }

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "ThemePack":
        return ThemePack(
            name=str(d.get("name", "Custom")),
            terrain_weights=dict(d.get("terrain_weights", {})),
            poi_list=list(d.get("poi_list", [])),
        )


# ---------- Labeling ----------
def hex_label(q: int, r: int) -> str:
    """
    Row letters like A..Z, AA..AZ, BA.. etc
    Column numbers 01..99.. (pads to 2 digits up to 99, then 3+ digits).
    """
    def to_letters(n: int) -> str:
        s = ""
        n = n + 1
        while n > 0:
            n, rem = divmod(n - 1, 26)
            s = chr(ord("A") + rem) + s
        return s

    col = q + 1
    # 2 digits up to 99, 3 digits beyond, etc
    width = 2 if col < 100 else (3 if col < 1000 else len(str(col)))
    return f"{to_letters(r)}{col:0{width}d}"


# ---------- Built-in themes ----------
BUILTIN_THEMES: Dict[str, ThemePack] = {
    "OSR": ThemePack(
        name="OSR",
        terrain_weights={
            "Plains": 30,
            "Forest": 22,
            "Hills": 16,
            "Mountains": 10,
            "Swamp": 8,
            "Desert": 7,
            "Water": 7,
        },
        poi_list=[
            "Ruins", "Dungeon Entrance", "Village", "Tower", "Monolith", "Shrine",
            "Wreck", "Cave", "Stronghold", "Standing Stones", "Obelisk", "Crater",
            "Fey Glade", "Ancient Tree", "Bandit Camp", "Witch Hut", "Watchpost"
        ],
    ),
    "Space": ThemePack(
        name="Space",
        terrain_weights={
            "Void": 30,
            "Dust Belt": 18,
            "Asteroids": 18,
            "Nebula": 12,
            "Ice": 10,
            "Radiation Zone": 7,
            "Derelict Field": 5,
        },
        poi_list=[
            "Derelict", "Beacon", "Anomaly", "Wreck", "Listening Post", "Refinery",
            "Pirate Den", "Warp Scar", "Forbidden Gate", "Bio-Sphere", "Debris Shrine"
        ],
    ),
    "Underdark": ThemePack(
        name="Underdark",
        terrain_weights={
            "Caverns": 28,
            "Fungus Forest": 18,
            "Chasm": 14,
            "Ruined Tunnels": 14,
            "Black Lake": 10,
            "Lava": 8,
            "Crystal Beds": 8,
        },
        poi_list=[
            "Ancient Door", "Collapsed Mine", "Cult Shrine", "Spore Grove", "Lost Outpost",
            "Chasm Bridge", "Buried Vault", "Mushroom Market", "Silent Monolith", "Deep Well"
        ],
    ),
}


# ---------- Core generation ----------
@dataclass
class HexMapConfig:
    width: int = 25
    height: int = 18
    seed: int = 1337
    poi_density: float = 0.08
    terrain_weights: Dict[str, float] = None
    poi_list: List[str] = None

    rivers_enabled: bool = False
    river_count: int = 1

    roads_enabled: bool = False
    road_count: int = 1

    def __post_init__(self):
        if self.terrain_weights is None:
            self.terrain_weights = dict(BUILTIN_THEMES["OSR"].terrain_weights)
        if self.poi_list is None:
            self.poi_list = list(BUILTIN_THEMES["OSR"].poi_list)


def _weighted_choice(rng: random.Random, weights: Dict[str, float]) -> str:
    items = list(weights.items())
    total = sum(max(0.0, float(w)) for _, w in items) or 1.0
    roll = rng.random() * total
    acc = 0.0
    for name, w in items:
        w = max(0.0, float(w))
        acc += w
        if roll <= acc:
            return name
    return items[-1][0]


def generate_hex_cells(cfg: HexMapConfig) -> Dict[Coord, HexCell]:
    rng = random.Random(cfg.seed)

    cells: Dict[Coord, HexCell] = {}
    for r in range(cfg.height):
        for q in range(cfg.width):
            terrain = _weighted_choice(rng, cfg.terrain_weights)
            poi = None
            if rng.random() < max(0.0, min(1.0, cfg.poi_density)) and cfg.poi_list:
                poi = rng.choice(cfg.poi_list)
            cells[(q, r)] = HexCell(q=q, r=r, terrain=terrain, poi=poi)
    return cells


def neighbors(q: int, r: int) -> List[Coord]:
    # odd-q vertical layout neighbors
    if q & 1:
        deltas = [(+1, 0), (+1, +1), (0, +1), (-1, +1), (-1, 0), (0, -1)]
    else:
        deltas = [(+1, -1), (+1, 0), (0, +1), (-1, 0), (-1, -1), (0, -1)]
    return [(q + dq, r + dr) for dq, dr in deltas]


def _in_bounds(cfg: HexMapConfig, q: int, r: int) -> bool:
    return 0 <= q < cfg.width and 0 <= r < cfg.height



# ---------- Travel costs & pathfinding ----------

_TERRAIN_KEYWORDS = [
    ("Water", "water"), ("Ocean", "water"), ("Sea", "water"), ("Lake", "water"), ("River", "water"),
    ("Coast", "coast"), ("Beach", "coast"),
    ("Mountain", "mountain"), ("Peak", "mountain"), ("Hills", "hills"),
    ("Forest", "forest"), ("Woods", "forest"), ("Jungle", "forest"),
    ("Swamp", "swamp"), ("Marsh", "swamp"), ("Bog", "swamp"),
    ("Desert", "desert"), ("Dunes", "desert"),
    ("Plains", "plains"), ("Grass", "plains"), ("Steppe", "plains"),
    ("Tundra", "tundra"), ("Snow", "tundra"), ("Ice", "tundra"),
    ("Cave", "cave"), ("Badlands", "badlands"), ("Ruins", "ruins"),
    # space-ish
    ("Void", "void"), ("Asteroids", "asteroids"), ("Nebula", "nebula"), ("Radiation", "radiation"),
    ("Derelict", "derelict"), ("Dust", "dust"),
]

def terrain_category(terrain: str) -> str:
    t = (terrain or "").strip()
    for k, cat in _TERRAIN_KEYWORDS:
        if k.lower() in t.lower():
            return cat
    return "generic"


def move_cost(terrain: str) -> float:
    cat = terrain_category(terrain)
    return {
        "plains": 1.0,
        "coast": 1.2,
        "forest": 1.6,
        "hills": 1.8,
        "swamp": 2.2,
        "desert": 2.0,
        "tundra": 2.0,
        "mountain": 3.0,
        "ruins": 1.4,
        "badlands": 2.0,
        "cave": 2.2,
        "water": 9999.0,     # impassable by default
        "void": 1.0,
        "dust": 1.4,
        "asteroids": 2.0,
        "nebula": 2.2,
        "radiation": 2.6,
        "derelict": 1.8,
        "generic": 1.5,
    }.get(cat, 1.5)


def _heuristic(a: Coord, b: Coord) -> float:
    # Simple axial-ish heuristic for odd-q vertical layout: use cube distance approximation
    aq, ar = a
    bq, br = b
    # Convert odd-q to cube coords approximation
    def to_cube(q: int, r: int):
        x = q
        z = r - (q - (q & 1)) // 2
        y = -x - z
        return x, y, z
    ax, ay, az = to_cube(aq, ar)
    bx, by, bz = to_cube(bq, br)
    return (abs(ax - bx) + abs(ay - by) + abs(az - bz)) / 2.0


def astar_path(cells: Dict[Coord, HexCell], start: Coord, goal: Coord) -> Optional[List[Coord]]:
    import heapq
    if start == goal:
        return [start]
    if start not in cells or goal not in cells:
        return None

    open_heap = []
    heapq.heappush(open_heap, (0.0, start))
    came_from: Dict[Coord, Coord] = {}
    g: Dict[Coord, float] = {start: 0.0}

    while open_heap:
        _, cur = heapq.heappop(open_heap)
        if cur == goal:
            # reconstruct
            path = [cur]
            while cur in came_from:
                cur = came_from[cur]
                path.append(cur)
            path.reverse()
            return path

        cq, cr = cur
        for nq, nr in neighbors(cq, cr):
            nxt = (nq, nr)
            if nxt not in cells:
                continue
            cost = move_cost(cells[nxt].terrain)
            if cost >= 9999.0:
                continue
            tentative = g[cur] + cost
            if tentative < g.get(nxt, 1e18):
                came_from[nxt] = cur
                g[nxt] = tentative
                f = tentative + _heuristic(nxt, goal)
                heapq.heappush(open_heap, (f, nxt))
    return None


# ---------- Settlements ----------

_SETTLEMENT_KINDS = ["Hamlet", "Village", "Town", "City", "Keep", "Outpost"]

_NAME_SYLLABLES = [
    "al","an","ar","ash","bar","bel","bra","bri","ca","car","cor","da","dar","del","dra",
    "el","en","far","fen","gar","hal","har","hel","il","in","jar","kel","kor","la","lor",
    "mar","mor","na","nor","or","os","ra","ran","rel","rin","sa","sar","sel","sha","sil",
    "ta","tar","tel","tor","ul","ur","val","ver","vor","wyn","yor","zan"
]

def generate_settlement_name(rng: random.Random) -> str:
    a = rng.choice(_NAME_SYLLABLES).title()
    b = rng.choice(_NAME_SYLLABLES)
    c = rng.choice(_NAME_SYLLABLES) if rng.random() < 0.35 else ""
    name = a + b + c
    # small polish
    name = re.sub(r"(.)\1\1+", r"\1\1", name)
    return name


def generate_settlements(cells: Dict[Coord, HexCell], cfg: HexMapConfig, rng: random.Random, count: int) -> List[Coord]:
    # Choose candidates preferring passable, lower-cost terrains and near edges less often.
    coords = list(cells.keys())
    if not coords or count <= 0:
        return []

    def score(c: Coord) -> float:
        cell = cells[c]
        base = 1.0 / max(0.5, move_cost(cell.terrain))
        # penalize water/mountains heavily
        cat = terrain_category(cell.terrain)
        if cat in ("water", "mountain", "void"):
            base *= 0.05
        # slight preference for varied terrain (pretend rivers exist)
        q, r = c
        edge = (q == 0 or r == 0 or q == cfg.width-1 or r == cfg.height-1)
        if edge:
            base *= 0.8
        # prefer cells with POI already a bit (become sites)
        if cell.poi:
            base *= 1.2
        return base

    weighted = [(score(c), c) for c in coords]
    # normalize weights
    total = sum(w for w,_ in weighted)
    if total <= 0:
        return []
    picks: List[Coord] = []
    for _ in range(min(count, len(coords))):
        x = rng.random() * total
        acc = 0.0
        chosen = weighted[-1][1]
        for w, c in weighted:
            acc += w
            if acc >= x:
                chosen = c
                break
        if chosen in picks:
            continue
        picks.append(chosen)
    # Assign to cells
    for i, c in enumerate(picks):
        kind = _SETTLEMENT_KINDS[min(len(_SETTLEMENT_KINDS)-1, int((i / max(1, len(picks)-1)) * (len(_SETTLEMENT_KINDS)-1)))]
        name = generate_settlement_name(rng)
        cells[c].settlement = {"name": name, "kind": kind}
        if not cells[c].poi:
            cells[c].poi = kind  # marker-friendly default
    return picks


def generate_road_network(cells: Dict[Coord, HexCell], settlements: List[Coord]) -> List[List[Coord]]:
    # Connect settlements using a simple MST on heuristic distance, then pathfind per edge.
    if len(settlements) < 2:
        return []
    remaining = set(settlements[1:])
    connected = {settlements[0]}
    roads: List[List[Coord]] = []

    while remaining:
        best = None
        best_pair = None
        for a in connected:
            for b in remaining:
                d = _heuristic(a, b)
                if best is None or d < best:
                    best = d
                    best_pair = (a, b)
        if not best_pair:
            break
        a, b = best_pair
        path = astar_path(cells, a, b)
        if path:
            roads.append(path)
        connected.add(b)
        remaining.remove(b)
    return roads


# ---------- Per-hex content cards ----------

_CONTENT = {
    "plains": {
        "encounters": ["Mounted scouts", "Grazing herd", "Wandering tinker", "Patrol of levy soldiers", "Storm-front refugees"],
        "hazards": ["Grassfire", "Sinkhole", "Flash hail", "Ambush-friendly tall grass"],
        "resources": ["Medicinal wildflower", "Game trails", "Salt lick", "Ancient boundary stones"],
    },
    "forest": {
        "encounters": ["Hunters with fresh bruises", "Lost child (or bait)", "Wolfpack shadowing you", "Fey lights", "Bandit snare line"],
        "hazards": ["Falling limb", "Thorn maze", "Miasma pocket", "Spore bloom"],
        "resources": ["Rare resin", "Edible mushrooms", "Good timber", "Hidden cache in hollow tree"],
    },
    "swamp": {
        "encounters": ["Bog-witch courier", "Swarm of biting insects", "Marsh raiders", "Frog-cult procession", "Wounded beast sinking"],
        "hazards": ["Quicksilt", "Rot-gas", "Leech bloom", "False ground"],
        "resources": ["Alchemical reeds", "Swamp pearls", "Black peat", "Blood-iron nodules"],
    },
    "hills": {
        "encounters": ["Goat-herders", "Hill giant tracks", "Roving mercenaries", "Stone-circle druids", "Rockslide survivors"],
        "hazards": ["Loose scree", "Sudden fog", "Cliffside collapse"],
        "resources": ["Tin seam", "Standing stones", "Eagle aeries", "Hidden spring"],
    },
    "mountain": {
        "encounters": ["Pilgrims on a hard vow", "Wyvern shadow", "Mine guards", "Hermit oracle", "Avalanche scouts"],
        "hazards": ["Avalanche", "Thin air", "Falling ice", "Narrow ledge"],
        "resources": ["Rich ore", "Cold-fire quartz", "Goat cheese caches", "Ancient pass markers"],
    },
    "desert": {
        "encounters": ["Caravan outriders", "Sand-skiff raiders", "Nomad water-barter", "Mirage pilgrims", "Scorpion shrine keepers"],
        "hazards": ["Sandstorm", "Heat mirage", "Dry well", "Glass-sand cuts"],
        "resources": ["Blue salt", "Fossil bed", "Star-metal fragment", "Hidden cistern"],
    },
    "tundra": {
        "encounters": ["Seal hunters", "White-fur bandits", "Aurora cult", "Lost expedition", "Ice-wolf pack"],
        "hazards": ["Whiteout", "Thin ice", "Frostbite wind", "Crevasse"],
        "resources": ["Amber ice", "Whale bone", "Warm-spring moss", "Meteorite grit"],
    },
    "water": {
        "encounters": ["River traders", "Crocodilian wake", "Fisherfolk omen", "Ghost lights", "Smuggler skiff"],
        "hazards": ["Strong current", "Hidden rocks", "Undertow"],
        "resources": ["Pearls", "Driftwood cache", "Freshwater spring", "Old mooring ring"],
    },
    "generic": {
        "encounters": ["Wandering pilgrims", "Suspicious travelers", "Scattered bones", "Distant drums", "A messenger with bad news"],
        "hazards": ["Sudden weather turn", "Bad footing", "Unseen watchers"],
        "resources": ["Lost coin-purse", "Useful herbs", "Old map fragment", "Scrap metal"],
    },
    # space-ish
    "nebula": {
        "encounters": ["Sensor ghosts", "Drifting prospector", "Cult beacon", "Pirate skiff", "Distress pings (looping)"],
        "hazards": ["Ion surge", "Zero-vis cloud", "Hull-eating spores"],
        "resources": ["Rare isotopes", "Electroplasm condensate", "Derelict pods"],
    },
    "asteroids": {
        "encounters": ["Salvage crew", "Automated defense drone", "Miner strike team", "Silent boarding party"],
        "hazards": ["Micrometeor swarm", "Unstable spin", "Explosive vent"],
        "resources": ["Rich ore asteroid", "Scrap hull plates", "Fuel cells"],
    },
    "radiation": {
        "encounters": ["Sealed-suit pilgrims", "Mutated scavengers", "Warning buoy", "Rogue AI relay"],
        "hazards": ["Dose spike", "EMP ripple", "Hot shards"],
        "resources": ["Shielding plates", "Rad-crystal", "Encrypted cache"],
    },
    "void": {
        "encounters": ["Nothing… then a blink", "Far signal", "Stowaway in your wake", "An echo of your ship"],
        "hazards": ["Navigation drift", "Comms blackout"],
        "resources": ["Signal triangulation", "Rare quiet", "Void-silk filament"],
    },
}

def generate_hex_content(terrain: str, rng: random.Random) -> Dict[str, List[str]]:
    cat = terrain_category(terrain)
    table = _CONTENT.get(cat) or _CONTENT["generic"]
    def pick(lst: List[str], n: int) -> List[str]:
        if not lst:
            return []
        n = max(1, min(n, len(lst)))
        items = lst[:]
        rng.shuffle(items)
        return items[:n]
    return {
        "encounters": pick(table.get("encounters", []), rng.randint(1, 3)),
        "hazards": pick(table.get("hazards", []), rng.randint(0, 2)),
        "resources": pick(table.get("resources", []), rng.randint(1, 3)),
    }




def _random_edge_cell(cfg: HexMapConfig, rng: random.Random) -> Coord:
    # Pick a random edge hex
    side = rng.choice(["top", "bottom", "left", "right"])
    if side == "top":
        return (rng.randrange(cfg.width), 0)
    if side == "bottom":
        return (rng.randrange(cfg.width), cfg.height - 1)
    if side == "left":
        return (0, rng.randrange(cfg.height))
    return (cfg.width - 1, rng.randrange(cfg.height))


def _random_walk_path(cfg: HexMapConfig, rng: random.Random, start: Coord, goal: Coord, max_steps: int = 500) -> List[Coord]:
    """
    Simple greedy/random walk toward goal. Not perfect A*, but fast and looks organic.
    """
    path = [start]
    current = start

    def dist(a: Coord, b: Coord) -> int:
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    visited = {start}
    for _ in range(max_steps):
        if current == goal:
            break
        nbs = [c for c in neighbors(*current) if _in_bounds(cfg, c[0], c[1])]
        if not nbs:
            break

        # prefer closer, but allow some randomness
        nbs.sort(key=lambda c: dist(c, goal))
        best = nbs[:3]  # take top few
        nxt = rng.choice(best) if rng.random() < 0.55 else nbs[0]

        # avoid infinite loops
        if nxt in visited and rng.random() < 0.85:
            # try next best unvisited
            unv = [c for c in nbs if c not in visited]
            if unv:
                nxt = unv[0]

        path.append(nxt)
        visited.add(nxt)
        current = nxt

    return path


def generate_rivers_and_roads(cfg: HexMapConfig, rng: random.Random) -> Tuple[List[List[Coord]], List[List[Coord]]]:
    rivers: List[List[Coord]] = []
    roads: List[List[Coord]] = []

    if cfg.rivers_enabled:
        for _ in range(max(0, cfg.river_count)):
            a = _random_edge_cell(cfg, rng)
            b = _random_edge_cell(cfg, rng)
            rivers.append(_random_walk_path(cfg, rng, a, b, max_steps=cfg.width * cfg.height))

    if cfg.roads_enabled:
        for _ in range(max(0, cfg.road_count)):
            a = _random_edge_cell(cfg, rng)
            b = _random_edge_cell(cfg, rng)
            roads.append(_random_walk_path(cfg, rng, a, b, max_steps=cfg.width * cfg.height))

    return rivers, roads


def build_key(cells: Dict[Coord, HexCell]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for c in cells.values():
        counts[c.terrain] = counts.get(c.terrain, 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])))


def build_poi_list(cells: Dict[Coord, HexCell]) -> List[str]:
    out: List[str] = []
    for c in cells.values():
        if not c.poi:
            continue
        out.append(f"{hex_label(c.q, c.r)} — {c.poi} ({c.terrain})")
    out.sort()
    return out


# ---------- Theme pack save/load ----------
def themes_dir(project_dir: Path) -> Path:
    d = project_dir / "themes"
    d.mkdir(parents=True, exist_ok=True)
    return d


def save_theme_pack(project_dir: Path, theme: ThemePack) -> Path:
    d = themes_dir(project_dir)
    safe = "".join(ch for ch in theme.name if ch.isalnum() or ch in (" ", "-", "_")).strip().replace(" ", "_")
    path = d / f"{safe}.json"
    path.write_text(json.dumps(theme.to_dict(), indent=2), encoding="utf-8")
    return path


def load_theme_packs(project_dir: Path) -> Dict[str, ThemePack]:
    packs: Dict[str, ThemePack] = dict(BUILTIN_THEMES)
    d = themes_dir(project_dir)
    for p in d.glob("*.json"):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            theme = ThemePack.from_dict(data)
            packs[theme.name] = theme
        except Exception:
            continue
    return packs
