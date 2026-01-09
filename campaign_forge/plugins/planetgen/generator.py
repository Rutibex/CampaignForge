from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional, Any
import math
import json
from pathlib import Path
from collections import deque


def _clamp(v: float, lo: float, hi: float) -> float:
    return lo if v < lo else hi if v > hi else v


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def _smoothstep(t: float) -> float:
    return t * t * (3.0 - 2.0 * t)


def _hash_u32(x: int) -> int:
    # xorshift-ish / mix
    x &= 0xFFFFFFFF
    x ^= x >> 16
    x = (x * 0x7feb352d) & 0xFFFFFFFF
    x ^= x >> 15
    x = (x * 0x846ca68b) & 0xFFFFFFFF
    x ^= x >> 16
    return x & 0xFFFFFFFF


def _hash2(seed: int, x: int, y: int) -> int:
    return _hash_u32(seed ^ _hash_u32(x * 374761393 + y * 668265263))


def _rand01(seed: int, x: int, y: int) -> float:
    return (_hash2(seed, x, y) & 0xFFFFFFFF) / 4294967295.0


def value_noise_2d(x: float, y: float, seed: int) -> float:
    # lattice value noise with smooth interpolation
    x0 = math.floor(x); y0 = math.floor(y)
    x1 = x0 + 1; y1 = y0 + 1
    tx = _smoothstep(x - x0)
    ty = _smoothstep(y - y0)
    v00 = _rand01(seed, x0, y0)
    v10 = _rand01(seed, x1, y0)
    v01 = _rand01(seed, x0, y1)
    v11 = _rand01(seed, x1, y1)
    a = _lerp(v00, v10, tx)
    b = _lerp(v01, v11, tx)
    return _lerp(a, b, ty)


def fbm_noise(x: float, y: float, seed: int, octaves: int = 5, lacunarity: float = 2.0, gain: float = 0.5) -> float:
    amp = 1.0
    freq = 1.0
    s = 0.0
    norm = 0.0
    for i in range(octaves):
        s += amp * value_noise_2d(x * freq, y * freq, seed + i * 1013)
        norm += amp
        amp *= gain
        freq *= lacunarity
    return s / norm if norm else 0.0


@dataclass
class PlanetGenConfig:
    preset_key: str = "fantasy"
    width: int = 512
    height: int = 256
    master_seed: int = 1337

    ocean_percent: float = 0.70
    plate_count: int = 18
    river_count: int = 220
    river_max_steps: int = 2600

    faction_count: int = 9
    settlement_count: int = 60

    # knobs
    ruggedness: float = 1.0
    temperature_bias: float = 0.0  # -0.2 colder, +0.2 hotter
    rainfall_bias: float = 0.0     # -0.2 drier, +0.2 wetter



    coast_smooth_iters: int = 3  # coastline cleanup iterations (removes thin spikes)
@dataclass
class PlanetWorld:
    cfg: PlanetGenConfig
    # per-cell arrays (len = w*h)
    elevation: List[float]
    ocean: List[bool]
    plates: List[int]
    moisture: List[float]
    temperature: List[float]
    biome: List[str]
    river: List[int]  # 0..255 intensity

    # civilization
    faction_id: List[int]          # -1 for none / ocean
    faction_strength: List[float]  # 0..1
    settlements: List[Dict[str, Any]]
    roads: List[List[Tuple[int, int]]]  # list of polylines
    pois: List[Dict[str, Any]]

    # overrides (sparse)
    overrides: Dict[str, Any]


def load_table(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def generate_world(cfg: PlanetGenConfig, tables_dir: Path, overrides: Optional[Dict[str, Any]] = None) -> PlanetWorld:
    """
    Deterministic world generation based on cfg.master_seed + cfg params.
    Overrides apply as sparse diffs (elevation_delta, biome_override, poi_edits).
    """
    w, h = cfg.width, cfg.height
    n = w * h
    seed = int(cfg.master_seed) & 0xFFFFFFFF

    overrides = overrides or {}
    elev_delta: Dict[str, float] = overrides.get("elevation_delta", {})  # key "x,y"
    biome_override: Dict[str, str] = overrides.get("biome_override", {})  # key "x,y" -> biome_id
    poi_edits: List[Dict[str, Any]] = overrides.get("poi_edits", [])  # list of POIs to force-add

    # ---- Plates (Voronoi) ----
    plate_pts: List[Tuple[int, int]] = []
    for i in range(max(2, cfg.plate_count)):
        px = int(_rand01(seed + 17, i * 97, 11) * w)
        py = int(_rand01(seed + 19, i * 97, 29) * h)
        plate_pts.append((px, py))

    plates = [0] * n
    for y in range(h):
        for x in range(w):
            best_i = 0
            best_d = 1e18
            # wrap in x for globe seam
            for i, (px, py) in enumerate(plate_pts):
                dx = abs(x - px)
                dx = min(dx, w - dx)
                dy = y - py
                d = dx * dx + dy * dy
                if d < best_d:
                    best_d = d
                    best_i = i
            plates[y * w + x] = best_i

    # boundary mask
    boundary = [0.0] * n
    for y in range(h):
        for x in range(w):
            i = y * w + x
            pid = plates[i]
            for oy in (-1, 0, 1):
                ny = y + oy
                if ny < 0 or ny >= h: 
                    continue
                for ox in (-1, 0, 1):
                    if ox == 0 and oy == 0:
                        continue
                    nx = (x + ox) % w
                    if plates[ny * w + nx] != pid:
                        boundary[i] = 1.0
                        break
                if boundary[i] == 1.0:
                    break

    # spread boundary (cheap blur)
    for _ in range(4):
        nb = [0.0] * n
        for y in range(h):
            for x in range(w):
                s = 0.0
                c = 0
                for oy in (-1, 0, 1):
                    ny = y + oy
                    if ny < 0 or ny >= h:
                        continue
                    for ox in (-1, 0, 1):
                        nx = (x + ox) % w
                        s += boundary[ny * w + nx]
                        c += 1
                nb[y * w + x] = s / c
        boundary = nb

    # ---- Elevation ----
    elevation = [0.0] * n
    scale = 1.6 / max(128, min(w, h))
    for y in range(h):
        lat = (y / (h - 1)) * 2.0 - 1.0  # -1..1
        lat_factor = 1.0 - (abs(lat) ** 1.7)  # less land at poles a bit
        for x in range(w):
            e = fbm_noise(x * scale, y * scale, seed + 101, octaves=6)
            e = (e - 0.5) * 1.8
            # add ridges from tectonic boundaries
            ridge = boundary[y * w + x]
            e += (ridge ** 1.6) * 0.95 * cfg.ruggedness
            # tweak by latitude (optional)
            e += (lat_factor - 0.55) * 0.08
            elevation[y * w + x] = e

    # apply elevation delta overrides
    for key, dv in elev_delta.items():
        try:
            xs, ys = key.split(",")
            x = int(xs); y = int(ys)
            if 0 <= x < w and 0 <= y < h:
                elevation[y * w + x] += float(dv)
        except Exception:
            continue

    # ---- Ocean mask by percentile ----
    sorted_e = sorted(elevation)
    ocean_thresh = sorted_e[int(_clamp(cfg.ocean_percent, 0.05, 0.95) * (n - 1))]
    ocean = [e <= ocean_thresh for e in elevation]

    # ---- Distance to ocean (for humidity/coasts) ----
    dist_ocean = [10**9] * n
    q = deque()
    for i, is_ocean in enumerate(ocean):
        if is_ocean:
            dist_ocean[i] = 0
            q.append(i)

    while q:
        i = q.popleft()
        d = dist_ocean[i] + 1
        x = i % w
        y = i // w
        for ox, oy in ((1,0),(-1,0),(0,1),(0,-1)):
            nx = (x + ox) % w
            ny = y + oy
            if ny < 0 or ny >= h:
                continue
            j = ny * w + nx
            if d < dist_ocean[j]:
                dist_ocean[j] = d
                q.append(j)

    # ---- Moisture + Temperature ----
    moisture = [0.0] * n
    temperature = [0.0] * n
    mscale = 2.2 / max(128, min(w, h))
    for y in range(h):
        lat = (y / (h - 1)) * 2.0 - 1.0
        base_temp = 1.0 - abs(lat)  # 0..1
        for x in range(w):
            i = y * w + x
            e = elevation[i]
            # lapse rate: higher elevation -> colder
            t = base_temp - _clamp((e - ocean_thresh) * 0.35, -0.3, 0.45)
            t += cfg.temperature_bias
            temperature[i] = _clamp(t, 0.0, 1.0)

            # moisture: noise + ocean proximity + orographic-ish effect
            m = fbm_noise(x * mscale, y * mscale, seed + 303, octaves=5)
            m = (m - 0.5) * 0.9 + 0.55
            coast_bonus = _clamp(1.0 - dist_ocean[i] / 40.0, 0.0, 1.0) * 0.25
            m += coast_bonus
            # rain shadow: high boundary ridges reduce moisture
            m -= _clamp(boundary[i] * 0.15, 0.0, 0.15)
            m += cfg.rainfall_bias
            moisture[i] = _clamp(m, 0.0, 1.0)

    # ---- Rivers ----
    river = [0] * n
    # candidate sources: high elevation land
    # pick deterministic pseudo-random points then accept if high enough
    srcs: List[Tuple[int,int]] = []
    attempts = cfg.river_count * 8
    for k in range(attempts):
        x = int(_rand01(seed + 777, k, 13) * w)
        y = int(_rand01(seed + 779, k, 31) * h)
        i = y * w + x
        if ocean[i]:
            continue
        if elevation[i] < ocean_thresh + 0.25:
            continue
        # spacing
        ok = True
        for sx, sy in srcs[-30:]:
            dx = abs(x - sx); dx = min(dx, w - dx)
            dy = y - sy
            if dx*dx + dy*dy < 12*12:
                ok = False
                break
        if ok:
            srcs.append((x,y))
        if len(srcs) >= cfg.river_count:
            break

    def downhill_step(x:int,y:int) -> Tuple[int,int]:
        i = y*w+x
        best = (x,y)
        best_e = elevation[i]
        for ox, oy in ((1,0),(-1,0),(0,1),(0,-1),(1,1),(-1,1),(1,-1),(-1,-1)):
            nx = (x+ox) % w
            ny = y+oy
            if ny < 0 or ny >= h:
                continue
            j = ny*w+nx
            ej = elevation[j]
            if ej < best_e:
                best_e = ej
                best = (nx,ny)
        return best

    for (sx,sy) in srcs:
        x,y = sx,sy
        for _ in range(cfg.river_max_steps):
            i = y*w+x
            if ocean[i]:
                break
            river[i] = min(255, river[i] + 24)
            nx, ny = downhill_step(x,y)
            if (nx,ny) == (x,y):
                # local sink: stop
                break
            x,y = nx,ny

    # ---- Biomes ----
    # load biome ids for mapping (colors handled elsewhere)
    biome = ["ocean"] * n
    for y in range(h):
        for x in range(w):
            i = y*w+x
            if ocean[i]:
                # sea ice at cold temps
                biome[i] = "sea_ice" if temperature[i] < 0.18 else "ocean"
                continue
            e = elevation[i]
            t = temperature[i]
            m = moisture[i]

            # mountains
            if e > ocean_thresh + 0.85:
                biome[i] = "snow_mountain" if t < 0.35 else "mountain"
                continue
            if e > ocean_thresh + 0.62:
                biome[i] = "highland"
                continue

            # wetlands near coasts / high moisture
            if m > 0.78 and e < ocean_thresh + 0.20:
                biome[i] = "marsh" if t < 0.45 else "swamp"
                continue

            # deserts
            if m < 0.22:
                biome[i] = "cold_desert" if t < 0.35 else "desert"
                continue

            # cold lands
            if t < 0.20:
                biome[i] = "tundra"
                continue
            if t < 0.32:
                biome[i] = "taiga" if m > 0.45 else "steppe"
                continue

            # temperate
            if t < 0.62:
                if m > 0.62:
                    biome[i] = "temperate_forest"
                elif m > 0.40:
                    biome[i] = "grassland"
                else:
                    biome[i] = "steppe"
                continue

            # tropical
            if m > 0.70:
                biome[i] = "tropical_rainforest"
            elif m > 0.42:
                biome[i] = "savanna"
            else:
                biome[i] = "badlands"

    # stamp rivers as biome river (for display)
    for i, rv in enumerate(river):
        if rv > 0 and not ocean[i]:
            biome[i] = "river"

    # apply biome overrides
    for key, bid in biome_override.items():
        try:
            xs, ys = key.split(",")
            x = int(xs); y = int(ys)
            if 0 <= x < w and 0 <= y < h:
                i = y*w+x
                if not ocean[i]:
                    biome[i] = str(bid)
        except Exception:
            continue

    # ---- Civilization generation (preset dependent) ----
    presets = load_table(tables_dir / "presets.json")["presets"]
    preset = presets.get(cfg.preset_key, presets["fantasy"])
    civ_level = int(preset.get("civ_level", 1))
    settlement_density = float(preset.get("settlement_density", 1.0))
    ruins_density = float(preset.get("ruins_density", 0.25))
    hazards = list(preset.get("hazards", []))
    faction_style = str(preset.get("faction_style", "feudal"))

    # factions - pick cores on land with spacing
    faction_count = max(0, int(cfg.faction_count)) if civ_level > 0 else max(3, int(cfg.faction_count // 2))
    faction_count = max(0, min(20, faction_count))

    faction_cores: List[Tuple[int,int]] = []
    attempts = max(1000, faction_count * 250)
    for k in range(attempts):
        x = int(_rand01(seed + 9001, k, 7) * w)
        y = int(_rand01(seed + 9003, k, 19) * h)
        i = y*w+x
        if ocean[i]:
            continue
        # prefer not-too-mountainous
        if elevation[i] > ocean_thresh + 0.75:
            continue
        ok = True
        for cx, cy in faction_cores:
            dx = abs(x - cx); dx = min(dx, w - dx)
            dy = y - cy
            if dx*dx + dy*dy < (w*h)**0.5:  # coarse spacing
                ok = False
                break
        if ok:
            faction_cores.append((x,y))
        if len(faction_cores) >= faction_count:
            break

    # influence: multi-source BFS in cost space (approx)
    faction_id = [-1] * n
    faction_strength = [0.0] * n
    if faction_cores:
        # initialize frontier with cores
        dist = [10**9] * n
        dq = deque()
        for fid,(cx,cy) in enumerate(faction_cores):
            i = cy*w+cx
            dist[i] = 0
            faction_id[i] = fid
            dq.append(i)

        while dq:
            i = dq.popleft()
            x = i % w; y = i // w
            fid = faction_id[i]
            nd = dist[i] + 1
            for ox,oy in ((1,0),(-1,0),(0,1),(0,-1)):
                nx = (x+ox) % w
                ny = y+oy
                if ny < 0 or ny >= h:
                    continue
                j = ny*w+nx
                if ocean[j]:
                    continue
                # movement cost depends on elevation/biome
                cost = 1
                if biome[j] in ("mountain","snow_mountain"):
                    cost = 3
                elif biome[j] in ("swamp","marsh"):
                    cost = 2
                if nd + (cost-1) < dist[j]:
                    dist[j] = nd + (cost-1)
                    faction_id[j] = fid
                    dq.append(j)

        # strength: decays with distance
        for i in range(n):
            if faction_id[i] >= 0 and not ocean[i]:
                d = dist[i]
                r = max(25, int((w + h) * 0.12))
                faction_strength[i] = math.exp(-d / r)

    # settlements
    settlements: List[Dict[str, Any]] = []
    if civ_level > 0:
        target = int(cfg.settlement_count * settlement_density)
        target = max(5, min(220, target))
        candidates: List[Tuple[float,int]] = []
        for y in range(h):
            for x in range(w):
                i = y*w+x
                if ocean[i]:
                    continue
                # suitability
                e = elevation[i]
                if e > ocean_thresh + 0.80:
                    continue
                m = moisture[i]
                t = temperature[i]
                coast = _clamp(1.0 - dist_ocean[i]/12.0, 0.0, 1.0)
                near_river = 1.0 if river[i] > 0 else 0.0
                suit = (0.35 + 0.5*m + 0.2*t) * (0.7 + 0.3*coast + 0.3*near_river)
                # prefer faction cores / centers
                if faction_id[i] >= 0:
                    suit *= (1.0 + 0.25*faction_strength[i])
                candidates.append((suit, i))
        candidates.sort(reverse=True, key=lambda t: t[0])

        def far_enough(ix:int) -> bool:
            x = ix % w; y = ix//w
            for s in settlements:
                sx,sy = s["x"], s["y"]
                dx = abs(x - sx); dx = min(dx, w - dx)
                dy = y - sy
                if dx*dx + dy*dy < 18*18:
                    return False
            return True

        k = 0
        while len(settlements) < target and k < len(candidates):
            _, ix = candidates[k]
            if far_enough(ix):
                x = ix % w; y = ix//w
                settlements.append({
                    "x": x, "y": y,
                    "kind": "town",
                    "faction": faction_id[ix],
                })
            k += 1

        # label top few as cities/capitals
        for i,s in enumerate(settlements[:max(3, min(8, len(settlements)//10))]):
            s["kind"] = "city" if i > 0 else "capital"

    # roads: simple connections between nearest neighbors (not pathfinding-heavy)
    roads: List[List[Tuple[int,int]]] = []
    if civ_level > 0 and len(settlements) >= 2:
        # connect each settlement to its nearest 2 neighbors
        pts = [(s["x"], s["y"]) for s in settlements]
        for idx,(x,y) in enumerate(pts):
            # compute distances
            dists = []
            for j,(x2,y2) in enumerate(pts):
                if j == idx: 
                    continue
                dx = abs(x-x2); dx = min(dx, w-dx)
                dy = y-y2
                dists.append((dx*dx+dy*dy, j))
            dists.sort()
            for _, j in dists[:2]:
                # polyline via bresenham
                x2,y2 = pts[j]
                poly = _bresenham_wrap(x,y,x2,y2,w,h)
                roads.append(poly)

    # POIs
    poi_tbl = load_table(tables_dir / "poi.json")
    nat = poi_tbl.get("natural", [])
    civ = poi_tbl.get("civilization", [])
    cat = poi_tbl.get("catastrophe", [])

    pois: List[Dict[str, Any]] = []
    # natural POIs weighted by biome variety
    desired_natural = max(24, int((w*h)**0.5 * 1.6))
    desired_civ = 0 if civ_level == 0 else max(18, int(len(settlements) * 0.45))
    desired_cat = max(6, int(desired_natural * 0.18))
    if cfg.preset_key == "apocalypse":
        desired_cat = max(desired_cat, int(desired_natural * 0.35))
        desired_civ = max(10, int(desired_civ * 0.7))

    def pick_poi_name(pool: List[str], k: int) -> str:
        if not pool:
            return f"POI-{k}"
        idx = int(_rand01(seed + 5511, k, 97) * len(pool))
        return pool[idx]

    def place_pois(count:int, pool: List[str], category: str, bias_ruins: bool=False):
        placed = 0
        tries = count * 20
        for k in range(tries):
            if placed >= count:
                break
            x = int(_rand01(seed + 6001 + hash(category) % 997, k, 17) * w)
            y = int(_rand01(seed + 6007 + hash(category) % 991, k, 33) * h)
            i = y*w+x
            if ocean[i]:
                continue
            # keep away from each other
            ok = True
            for p in pois[-80:]:
                dx = abs(x - p["x"]); dx = min(dx, w - dx)
                dy = y - p["y"]
                if dx*dx + dy*dy < 14*14:
                    ok = False
                    break
            if not ok:
                continue
            # suitability
            if category == "civilization" and civ_level > 0:
                # near settlements
                near = 0
                for s in settlements[:60]:
                    dx = abs(x-s["x"]); dx = min(dx, w-dx)
                    dy = y-s["y"]
                    if dx*dx+dy*dy < 20*20:
                        near = 1
                        break
                if near == 0:
                    continue
            if bias_ruins:
                # favor areas with factions/roads
                if faction_id[i] < 0:
                    continue
            name = pick_poi_name(pool, k + placed*7)
            pois.append({
                "x": x, "y": y,
                "name": name,
                "category": category,
                "biome": biome[i],
                "faction": faction_id[i],
            })
            placed += 1

    place_pois(desired_natural, nat, "natural")
    if civ_level > 0:
        place_pois(desired_civ, civ, "civilization", bias_ruins=True)
    place_pois(desired_cat, cat, "catastrophe")

    # add ruins overlay based on preset (represented as POIs)
    extra_ruins = int(desired_natural * ruins_density * 0.6)
    if civ_level > 0 and extra_ruins > 0:
        ruins_pool = [p for p in civ if "Ruins" in p or "Abandoned" in p or "Collapsed" in p] or civ
        place_pois(extra_ruins, ruins_pool, "civilization", bias_ruins=True)

    # apply GM forced POIs
    for p in poi_edits:
        try:
            x = int(p.get("x", 0)); y = int(p.get("y", 0))
            if 0 <= x < w and 0 <= y < h and not ocean[y*w+x]:
                pois.append({
                    "x": x, "y": y,
                    "name": str(p.get("name","Custom POI")),
                    "category": str(p.get("category","custom")),
                    "biome": biome[y*w+x],
                    "faction": int(p.get("faction",-1)),
                    "notes": str(p.get("notes","")).strip(),
                })
        except Exception:
            continue

    return PlanetWorld(
        cfg=cfg,
        elevation=elevation,
        ocean=ocean,
        plates=plates,
        moisture=moisture,
        temperature=temperature,
        biome=biome,
        river=river,
        faction_id=faction_id,
        faction_strength=faction_strength,
        settlements=settlements,
        roads=roads,
        pois=pois,
        overrides=overrides,
    )


def _bresenham_wrap(x0:int, y0:int, x1:int, y1:int, w:int, h:int) -> List[Tuple[int,int]]:
    # shortest wrap in x direction
    dx = x1 - x0
    if abs(dx) > w//2:
        if dx > 0:
            x1 -= w
        else:
            x1 += w

    points: List[Tuple[int,int]] = []
    x, y = x0, y0
    dx = abs(x1 - x0)
    sx = 1 if x0 < x1 else -1
    dy = -abs(y1 - y0)
    sy = 1 if y0 < y1 else -1
    err = dx + dy
    while True:
        points.append((x % w, _clamp_int(y, 0, h-1)))
        if x == x1 and y == y1:
            break
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x += sx
        if e2 <= dx:
            err += dx
            y += sy
        if len(points) > w*h:
            break
    return points


def _clamp_int(v:int, lo:int, hi:int) -> int:
    return lo if v < lo else hi if v > hi else v
