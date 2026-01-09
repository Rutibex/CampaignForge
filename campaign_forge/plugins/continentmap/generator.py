from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple, Dict, Any
import math
import heapq
import random


# ----------------------------
# Models
# ----------------------------

@dataclass
class Faction:
    fid: int
    name: str
    kind: str
    capital: Tuple[int, int]  # (x, y)
    # Color is stored as RGB tuple (renderer uses this)
    color: Tuple[int, int, int]


@dataclass
class ContinentModel:
    w: int
    h: int
    seed: int

    # Scalar layers in [0,1]
    elev: List[float]
    moist: List[float]
    temp: List[float]  # already includes latitude influence

    land: List[bool]

    # Derived layers
    biome: List[int]               # small int code per cell
    river: List[bool]              # simple river mask
    faction: List[int]             # -1 = none, else faction id
    contested: List[bool]          # borderlands / close influence

    factions: List[Faction]
    notes: Dict[str, Any]          # summary stats, names, etc.

    def idx(self, x: int, y: int) -> int:
        return y * self.w + x


# ----------------------------
# Noise helpers (pure python)
# ----------------------------

def _clamp01(x: float) -> float:
    if x < 0.0:
        return 0.0
    if x > 1.0:
        return 1.0
    return x

def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t

def _fade(t: float) -> float:
    # smootherstep-ish
    return t * t * (3.0 - 2.0 * t)

def _hash2i(seed: int, xi: int, yi: int) -> int:
    # deterministic integer hash -> 32-bit
    n = seed ^ (xi * 374761393) ^ (yi * 668265263)
    n = (n ^ (n >> 13)) * 1274126177
    n = n ^ (n >> 16)
    return n & 0xFFFFFFFF

def _rand01(seed: int, xi: int, yi: int) -> float:
    return _hash2i(seed, xi, yi) / 4294967295.0

def value_noise(seed: int, x: float, y: float, period: int) -> float:
    """
    Smooth value noise over integer lattice.
    period controls feature size: larger = smoother/bigger blobs.
    """
    fx = x / period
    fy = y / period
    x0 = math.floor(fx)
    y0 = math.floor(fy)
    tx = fx - x0
    ty = fy - y0
    tx = _fade(tx)
    ty = _fade(ty)

    v00 = _rand01(seed, x0, y0)
    v10 = _rand01(seed, x0 + 1, y0)
    v01 = _rand01(seed, x0, y0 + 1)
    v11 = _rand01(seed, x0 + 1, y0 + 1)

    a = _lerp(v00, v10, tx)
    b = _lerp(v01, v11, tx)
    return _lerp(a, b, ty)

def fbm(seed: int, x: float, y: float, base_period: int, octaves: int = 5, lacunarity: float = 2.0, gain: float = 0.5) -> float:
    """
    Fractal Brownian Motion (stacked value noise).
    Returns approx [0,1].
    """
    amp = 1.0
    freq = 1.0
    total = 0.0
    norm = 0.0
    for i in range(max(1, octaves)):
        p = max(2, int(base_period / freq))
        total += amp * value_noise(seed + i * 1013, x, y, p)
        norm += amp
        amp *= gain
        freq *= lacunarity
    return total / norm if norm > 0 else 0.0

def domain_warp(seed: int, x: float, y: float, warp_period: int, warp_strength: float) -> Tuple[float, float]:
    wx = fbm(seed + 9001, x, y, warp_period, octaves=3) * 2.0 - 1.0
    wy = fbm(seed + 9002, x, y, warp_period, octaves=3) * 2.0 - 1.0
    return (x + wx * warp_strength, y + wy * warp_strength)


# ----------------------------
# Generation
# ----------------------------

BIOME_OCEAN = 0
BIOME_BEACH = 1
BIOME_TUNDRA = 2
BIOME_TAIGA = 3
BIOME_TEMPERATE_FOREST = 4
BIOME_GRASSLAND = 5
BIOME_DESERT = 6
BIOME_SAVANNA = 7
BIOME_TROPICAL_FOREST = 8
BIOME_MOUNTAIN = 9
BIOME_SNOW_PEAK = 10

_BIOME_NAMES = {
    BIOME_OCEAN: "Ocean",
    BIOME_BEACH: "Beach",
    BIOME_TUNDRA: "Tundra",
    BIOME_TAIGA: "Taiga",
    BIOME_TEMPERATE_FOREST: "Temperate Forest",
    BIOME_GRASSLAND: "Grassland",
    BIOME_DESERT: "Desert",
    BIOME_SAVANNA: "Savanna",
    BIOME_TROPICAL_FOREST: "Tropical Forest",
    BIOME_MOUNTAIN: "Mountain",
    BIOME_SNOW_PEAK: "Snow Peak",
}

def generate_continent(
    *,
    seed: int,
    w: int,
    h: int,
    sea_level: float = 0.50,
    ruggedness: float = 0.60,
    coastline: float = 0.65,
    moisture: float = 0.55,
    temperature: float = 0.55,
    river_density: float = 0.35,
    add_islands: bool = True,
    factions_n: int = 8,
    contested_band: float = 0.20,
) -> ContinentModel:
    """
    Pure generation. No Qt. Designed for ~128..512 sizes (cells), not pixels.
    """
    rng = random.Random(seed)

    elev: List[float] = [0.0] * (w * h)
    moist: List[float] = [0.0] * (w * h)
    temp: List[float] = [0.0] * (w * h)
    land: List[bool] = [False] * (w * h)
    biome: List[int] = [BIOME_OCEAN] * (w * h)
    river: List[bool] = [False] * (w * h)
    faction: List[int] = [-1] * (w * h)
    contested: List[bool] = [False] * (w * h)

    # --- Build a "continent mask" (one main landmass) ---
    # Use warped noise + a radial falloff so the biggest land tends to stay near center.
    cx = (w - 1) / 2.0
    cy = (h - 1) / 2.0
    maxr = math.sqrt(cx * cx + cy * cy)

    base_period = max(16, int(min(w, h) * (0.18 + 0.22 * (1.0 - coastline))))
    warp_period = max(12, int(min(w, h) * 0.12))
    warp_strength = 18.0 * (0.5 + 0.8 * coastline)

    for y in range(h):
        lat = abs((y / (h - 1)) * 2.0 - 1.0)  # 0 at equator-ish center, 1 at extremes
        for x in range(w):
            i = y * w + x

            wx, wy = domain_warp(seed + 100, float(x), float(y), warp_period, warp_strength)
            n = fbm(seed + 200, wx, wy, base_period, octaves=5)

            # radial falloff: encourages single continent
            dx = x - cx
            dy = y - cy
            r = math.sqrt(dx * dx + dy * dy) / maxr
            falloff = 1.0 - (r ** (1.6 + 1.2 * (1.0 - coastline)))

            # optionally sprinkle islands with another noise
            isl = fbm(seed + 777, x, y, max(10, base_period // 2), octaves=3)
            isl = (isl - 0.55) * (0.25 if add_islands else 0.0)

            e = (0.72 * n + 0.55 * falloff + isl) / (0.72 + 0.55)
            # ruggedness increases variance: push away from mid
            e = (e - 0.5) * (0.7 + 1.2 * ruggedness) + 0.5
            e = _clamp01(e)

            elev[i] = e

            # moisture & temperature fields
            m = fbm(seed + 300, wx, wy, max(10, base_period), octaves=4)
            m = _clamp01((m - 0.5) * (0.65 + 0.8 * moisture) + 0.5)

            # temperature: latitude + noise; "temperature" knob shifts warmer/colder
            t_noise = fbm(seed + 400, x, y, max(14, base_period), octaves=3)
            base_t = 1.0 - lat  # warm in middle
            t = 0.70 * base_t + 0.30 * t_noise
            t = _clamp01((t - 0.5) * (0.7 + 0.9 * temperature) + 0.5)

            moist[i] = m
            temp[i] = t

    # --- Land / Sea ---
    for i in range(w * h):
        land[i] = elev[i] >= sea_level

    # --- Rivers (simple downhill tracing from high points) ---
    # We'll mark a thin mask; good enough for visual + hooks.
    # Choose sources from high elevation & moist-ish.
    sources: List[int] = []
    attempts = int(w * h * (0.002 + 0.01 * river_density))
    for _ in range(attempts):
        x = rng.randrange(0, w)
        y = rng.randrange(0, h)
        i = y * w + x
        if not land[i]:
            continue
        if elev[i] < (sea_level + 0.25):
            continue
        if moist[i] < 0.35:
            continue
        sources.append(i)

    def neighbors(ix: int) -> List[int]:
        x = ix % w
        y = ix // w
        out = []
        if x > 0: out.append(ix - 1)
        if x < w - 1: out.append(ix + 1)
        if y > 0: out.append(ix - w)
        if y < h - 1: out.append(ix + w)
        return out

    for src in sources[: min(len(sources), 500)]:
        cur = src
        steps = 0
        while steps < (w + h) * 2:
            steps += 1
            if not land[cur]:
                break
            river[cur] = True
            # move to lowest neighbor
            nbs = neighbors(cur)
            nxt = min(nbs, key=lambda j: elev[j])
            if elev[nxt] >= elev[cur] - 1e-6:
                break
            cur = nxt

    # --- Biomes ---
    for y in range(h):
        for x in range(w):
            i = y * w + x
            if not land[i]:
                biome[i] = BIOME_OCEAN
                continue

            e = elev[i]
            m = moist[i]
            t = temp[i]

            # beach band
            if e < sea_level + 0.03:
                biome[i] = BIOME_BEACH
                continue

            # mountains
            if e > sea_level + 0.42:
                biome[i] = BIOME_SNOW_PEAK if t < 0.35 else BIOME_MOUNTAIN
                continue

            # cold biomes
            if t < 0.25:
                biome[i] = BIOME_TUNDRA
            elif t < 0.38:
                biome[i] = BIOME_TAIGA
            else:
                # warm biomes based on moisture
                if m < 0.22:
                    biome[i] = BIOME_DESERT if t > 0.45 else BIOME_GRASSLAND
                elif m < 0.40:
                    biome[i] = BIOME_GRASSLAND if t < 0.65 else BIOME_SAVANNA
                else:
                    biome[i] = BIOME_TEMPERATE_FOREST if t < 0.70 else BIOME_TROPICAL_FOREST

    # --- Factions ---
    factions = _generate_factions(seed=seed, land=land, biome=biome, elev=elev, moist=moist, temp=temp, w=w, h=h, n=factions_n)
    if factions:
        _assign_faction_territory(
            w=w,
            h=h,
            land=land,
            biome=biome,
            elev=elev,
            river=river,
            factions=factions,
            out_faction=faction,
            out_contested=contested,
            contested_band=contested_band,
        )

    # --- Notes summary ---
    land_cells = sum(1 for v in land if v)
    notes = {
        "seed": seed,
        "size": [w, h],
        "sea_level": sea_level,
        "land_pct": (land_cells / (w * h)) if w * h else 0.0,
        "factions_n": len(factions),
        "biome_counts": _count_biomes(biome),
    }

    return ContinentModel(
        w=w, h=h, seed=seed,
        elev=elev, moist=moist, temp=temp,
        land=land,
        biome=biome,
        river=river,
        faction=faction,
        contested=contested,
        factions=factions,
        notes=notes,
    )


def _count_biomes(biome: List[int]) -> Dict[str, int]:
    counts: Dict[int, int] = {}
    for b in biome:
        counts[b] = counts.get(b, 0) + 1
    out: Dict[str, int] = {}
    for k, v in counts.items():
        out[_BIOME_NAMES.get(k, str(k))] = v
    return dict(sorted(out.items(), key=lambda kv: kv[1], reverse=True))


def _generate_factions(
    *,
    seed: int,
    land: List[bool],
    biome: List[int],
    elev: List[float],
    moist: List[float],
    temp: List[float],
    w: int,
    h: int,
    n: int
) -> List[Faction]:
    rng = random.Random(seed + 5000)
    n = max(0, min(int(n), 24))
    if n <= 0:
        return []

    # Candidate capitals: land, not mountain peak, not beach, not tiny island-y (heuristic via elevation)
    candidates: List[int] = []
    for i in range(w * h):
        if not land[i]:
            continue
        b = biome[i]
        if b in (BIOME_BEACH, BIOME_SNOW_PEAK):
            continue
        if b == BIOME_MOUNTAIN and temp[i] < 0.40:
            continue
        if elev[i] < 0.52:
            candidates.append(i)

    if not candidates:
        return []

    # Spread capitals using simple "poisson-ish" rejection
    capitals: List[int] = []
    min_dist = max(10, int(min(w, h) * 0.08))
    tries = 0
    while len(capitals) < n and tries < n * 600:
        tries += 1
        c = candidates[rng.randrange(0, len(candidates))]
        cx, cy = c % w, c // w
        ok = True
        for prev in capitals:
            px, py = prev % w, prev // w
            if (cx - px) ** 2 + (cy - py) ** 2 < (min_dist ** 2):
                ok = False
                break
        if ok:
            capitals.append(c)

    # If we couldn't place enough, fill randomly
    while len(capitals) < n and candidates:
        capitals.append(candidates[rng.randrange(0, len(candidates))])

    # Name generation: simple internal lists (you can swap to Names module later)
    prefixes = ["Iron", "Storm", "Ash", "Verdant", "Gilded", "Amber", "Obsidian", "Silver", "Sable", "Crimson", "Ivory", "Cedar", "Wyrm", "Dawn", "Hollow"]
    nouns = ["Crown", "March", "League", "Throne", "Banner", "Pact", "Covenant", "Dominion", "Hearth", "Order", "Khanate", "Freeholds", "Syndicate", "Principality"]
    kinds = ["Kingdom", "Empire", "Free Cities", "Horde", "Theocracy", "Merchant League", "Duchy", "Confederacy", "Magocracy"]

    # Colors: bright-ish distinct palette
    palette = [
        (220, 70, 70), (70, 160, 220), (90, 200, 120), (200, 160, 60),
        (170, 90, 210), (60, 200, 200), (220, 120, 50), (120, 120, 220),
        (200, 90, 140), (90, 180, 80), (160, 110, 70), (90, 90, 90),
    ]

    factions: List[Faction] = []
    for fid, cap in enumerate(capitals[:n]):
        name = f"{rng.choice(prefixes)} {rng.choice(nouns)}"
        kind = rng.choice(kinds)
        x, y = cap % w, cap // w
        color = palette[fid % len(palette)]
        factions.append(Faction(fid=fid, name=name, kind=kind, capital=(x, y), color=color))
    return factions


def _terrain_cost(b: int, e: float, has_river: bool) -> float:
    # Travel/expansion cost for border shaping
    cost = 1.0
    if b in (BIOME_MOUNTAIN, BIOME_SNOW_PEAK):
        cost += 3.0
    elif b in (BIOME_TAIGA, BIOME_TUNDRA):
        cost += 1.4
    elif b in (BIOME_TROPICAL_FOREST, BIOME_TEMPERATE_FOREST):
        cost += 1.0
    elif b in (BIOME_DESERT,):
        cost += 1.8
    elif b in (BIOME_GRASSLAND, BIOME_SAVANNA):
        cost += 0.4
    if has_river:
        cost -= 0.15
    # steeper slopes slightly harder (cheap approximation)
    cost += max(0.0, (e - 0.55) * 0.8)
    return max(0.2, cost)


def _assign_faction_territory(
    *,
    w: int,
    h: int,
    land: List[bool],
    biome: List[int],
    elev: List[float],
    river: List[bool],
    factions: List[Faction],
    out_faction: List[int],
    out_contested: List[bool],
    contested_band: float,
) -> None:
    """
    Multi-source Dijkstra flood: each capital expands with terrain cost.
    Also tracks second-best distance to flag contested borderlands.
    """
    INF = 10**18
    best_d = [INF] * (w * h)
    best_f = [-1] * (w * h)
    second_d = [INF] * (w * h)

    pq: List[Tuple[float, int, int]] = []  # (dist, idx, fid)

    def push(i: int, fid: int, dist: float):
        heapq.heappush(pq, (dist, i, fid))

    for f in factions:
        x, y = f.capital
        i = y * w + x
        if 0 <= i < w * h and land[i]:
            best_d[i] = 0.0
            best_f[i] = f.fid
            push(i, f.fid, 0.0)

    def nbs(i: int) -> List[int]:
        x = i % w
        y = i // w
        out = []
        if x > 0: out.append(i - 1)
        if x < w - 1: out.append(i + 1)
        if y > 0: out.append(i - w)
        if y < h - 1: out.append(i + w)
        return out

    while pq:
        d, i, fid = heapq.heappop(pq)
        if d > best_d[i] + 1e-9 and fid == best_f[i]:
            continue
        if not land[i]:
            continue

        for j in nbs(i):
            if not land[j]:
                continue
            step = _terrain_cost(biome[j], elev[j], river[j])
            nd = d + step

            if fid == best_f[j]:
                # same owner improvement
                if nd + 1e-9 < best_d[j]:
                    best_d[j] = nd
                    push(j, fid, nd)
            else:
                # new contender
                if nd + 1e-9 < best_d[j]:
                    # shift best -> second
                    second_d[j] = best_d[j]
                    best_d[j] = nd
                    best_f[j] = fid
                    push(j, fid, nd)
                elif nd + 1e-9 < second_d[j]:
                    second_d[j] = nd

    # Write outputs
    # Contested: second-best close to best
    # contested_band ~ fraction of best distance; + small absolute for near capitals
    for i in range(w * h):
        out_faction[i] = best_f[i] if land[i] else -1
        if not land[i]:
            out_contested[i] = False
            continue
        bd = best_d[i]
        sd = second_d[i]
        if sd >= INF or bd <= 1e-9:
            out_contested[i] = False
            continue
        margin = sd - bd
        thresh = max(1.5, bd * float(contested_band))
        out_contested[i] = margin <= thresh


def biome_name(code: int) -> str:
    return _BIOME_NAMES.get(code, f"Biome#{code}")
