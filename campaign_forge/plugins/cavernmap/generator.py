# -------------------------
# generator.py
# -------------------------
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional
import math
import random
from collections import deque


Cell = int  # 0 = wall, 1 = floor


@dataclass
class CavernParams:
    width: int = 80
    height: int = 60

    # CA seeding + smoothing
    fill_percent: int = 48            # initial random walls %
    smooth_steps: int = 5             # number of CA iterations
    birth_limit: int = 5              # >= this many wall neighbors -> become wall
    death_limit: int = 3              # <= this many wall neighbors -> become floor
    border_walls: bool = True         # force border walls

    # Connectivity + cleanup
    keep_largest_region: bool = True
    min_region_size: int = 50         # remove small floor islands
    min_wall_region_size: int = 50    # optional: remove tiny wall islands (not essential)

    # Post-processing
    widen_passes: int = 0             # optional: widen corridors by eroding walls
    close_small_holes: bool = True    # optional pass to close tiny holes
    add_chokepoints: int = 0          # optional: attempt to create narrow chokepoints

    # Biome overlay (very simple & deterministic)
    biome_mode: str = "simple"        # "simple" only in MVP
    biome_count: int = 4              # number of biome seeds
    biome_spread_steps: int = 2000    # BFS steps for biome spread


@dataclass
class CavernRegion:
    id: int
    cells: List[Tuple[int, int]]
    bbox: Tuple[int, int, int, int]
    size: int
    kind: str                 # "chamber" | "tunnel" | "cavern" | "pocket"
    exits: int                # approx boundary-exit count
    name: str                 # generated label
    biome: str                # assigned biome tag


@dataclass
class CavernResult:
    width: int
    height: int
    grid: List[List[Cell]]            # [y][x]
    seed: int
    regions: List[CavernRegion]
    biome_grid: List[List[str]]       # [y][x] biome name for floors, "" for walls
    stats: Dict[str, float]


# ---------- CA Core ----------

def _rand_bool(rng: random.Random, percent_true: int) -> bool:
    return rng.randint(0, 99) < percent_true

def _in_bounds(x: int, y: int, w: int, h: int) -> bool:
    return 0 <= x < w and 0 <= y < h

def _count_wall_neighbors(grid: List[List[Cell]], x: int, y: int) -> int:
    h = len(grid)
    w = len(grid[0]) if h else 0
    count = 0
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dx == 0 and dy == 0:
                continue
            nx, ny = x + dx, y + dy
            if not _in_bounds(nx, ny, w, h):
                count += 1  # treat out-of-bounds as wall
            else:
                if grid[ny][nx] == 0:
                    count += 1
    return count

def _init_grid(params: CavernParams, rng: random.Random) -> List[List[Cell]]:
    grid = []
    for y in range(params.height):
        row = []
        for x in range(params.width):
            if params.border_walls and (x == 0 or y == 0 or x == params.width - 1 or y == params.height - 1):
                row.append(0)
            else:
                # True means wall
                is_wall = _rand_bool(rng, params.fill_percent)
                row.append(0 if is_wall else 1)
        grid.append(row)
    return grid

def _smooth(grid: List[List[Cell]], params: CavernParams) -> List[List[Cell]]:
    h = len(grid)
    w = len(grid[0]) if h else 0
    new_grid = [[0 for _ in range(w)] for _ in range(h)]
    for y in range(h):
        for x in range(w):
            walls = _count_wall_neighbors(grid, x, y)
            if grid[y][x] == 0:
                # currently wall
                if walls < params.death_limit:
                    new_grid[y][x] = 1
                else:
                    new_grid[y][x] = 0
            else:
                # currently floor
                if walls > params.birth_limit:
                    new_grid[y][x] = 0
                else:
                    new_grid[y][x] = 1
    if params.border_walls:
        for x in range(w):
            new_grid[0][x] = 0
            new_grid[h - 1][x] = 0
        for y in range(h):
            new_grid[y][0] = 0
            new_grid[y][w - 1] = 0
    return new_grid

# ---------- Region extraction ----------

def _flood_collect(grid: List[List[Cell]], start: Tuple[int, int], target: Cell, visited: List[List[bool]]) -> List[Tuple[int, int]]:
    h = len(grid); w = len(grid[0])
    sx, sy = start
    q = deque([(sx, sy)])
    visited[sy][sx] = True
    out = []
    while q:
        x, y = q.popleft()
        out.append((x, y))
        for dx, dy in ((1,0),(-1,0),(0,1),(0,-1)):
            nx, ny = x + dx, y + dy
            if _in_bounds(nx, ny, w, h) and (not visited[ny][nx]) and grid[ny][nx] == target:
                visited[ny][nx] = True
                q.append((nx, ny))
    return out

def _regions_of_type(grid: List[List[Cell]], target: Cell) -> List[List[Tuple[int, int]]]:
    h = len(grid); w = len(grid[0])
    visited = [[False for _ in range(w)] for _ in range(h)]
    regions = []
    for y in range(h):
        for x in range(w):
            if not visited[y][x] and grid[y][x] == target:
                reg = _flood_collect(grid, (x, y), target, visited)
                regions.append(reg)
    return regions

def _remove_small_regions(grid: List[List[Cell]], target: Cell, min_size: int) -> None:
    regions = _regions_of_type(grid, target)
    if not regions:
        return
    for reg in regions:
        if len(reg) < min_size:
            # flip to opposite
            for (x, y) in reg:
                grid[y][x] = 1 - target

def _keep_largest_floor_region(grid: List[List[Cell]]) -> None:
    floor_regions = _regions_of_type(grid, 1)
    if not floor_regions:
        return
    floor_regions.sort(key=len, reverse=True)
    keep = set(floor_regions[0])
    h = len(grid); w = len(grid[0])
    for y in range(h):
        for x in range(w):
            if grid[y][x] == 1 and (x, y) not in keep:
                grid[y][x] = 0

# ---------- Post-processing ----------

def _widen(grid: List[List[Cell]], passes: int) -> None:
    # Very simple widening: for each pass, convert walls with many floor neighbors to floor
    h = len(grid); w = len(grid[0])
    for _ in range(passes):
        to_floor = []
        for y in range(1, h - 1):
            for x in range(1, w - 1):
                if grid[y][x] == 0:
                    floor_n = 0
                    for dx, dy in ((1,0),(-1,0),(0,1),(0,-1)):
                        if grid[y+dy][x+dx] == 1:
                            floor_n += 1
                    if floor_n >= 3:
                        to_floor.append((x, y))
        for x, y in to_floor:
            grid[y][x] = 1

def _close_tiny_holes(grid: List[List[Cell]]) -> None:
    # Close 1-cell holes surrounded by walls
    h = len(grid); w = len(grid[0])
    to_wall = []
    for y in range(1, h - 1):
        for x in range(1, w - 1):
            if grid[y][x] == 1:
                # if all 4-neighbors are walls, it's a tiny pocket
                if grid[y-1][x] == 0 and grid[y+1][x] == 0 and grid[y][x-1] == 0 and grid[y][x+1] == 0:
                    to_wall.append((x, y))
    for x, y in to_wall:
        grid[y][x] = 0

# ---------- Region labeling / typing ----------

_BIOMES = [
    "Limestone",
    "Fungal",
    "Crystal",
    "Flooded",
    "Volcanic",
    "Bonefield",
    "Slime",
    "Ruins",
]

def _pick_biomes(rng: random.Random, k: int) -> List[str]:
    pool = _BIOMES[:]
    rng.shuffle(pool)
    return pool[:max(1, min(k, len(pool)))]

def _biome_spread(grid: List[List[Cell]], rng: random.Random, params: CavernParams) -> List[List[str]]:
    h = len(grid); w = len(grid[0])
    biome_grid = [["" for _ in range(w)] for _ in range(h)]
    floors = [(x, y) for y in range(h) for x in range(w) if grid[y][x] == 1]
    if not floors:
        return biome_grid

    biome_names = _pick_biomes(rng, params.biome_count)
    seeds = []
    for i in range(len(biome_names)):
        seeds.append((biome_names[i], floors[rng.randrange(0, len(floors))]))

    q = deque()
    for name, (x, y) in seeds:
        biome_grid[y][x] = name
        q.append((x, y))

    steps = 0
    while q and steps < params.biome_spread_steps:
        x, y = q.popleft()
        name = biome_grid[y][x]
        for dx, dy in ((1,0),(-1,0),(0,1),(0,-1)):
            nx, ny = x+dx, y+dy
            if _in_bounds(nx, ny, w, h) and grid[ny][nx] == 1 and biome_grid[ny][nx] == "":
                # small randomness to create mottling
                if rng.random() < 0.85:
                    biome_grid[ny][nx] = name
                    q.append((nx, ny))
        steps += 1

    # any remaining floors unassigned -> nearest-ish fill via second pass
    # (cheap: assign from a random neighbor)
    for y in range(h):
        for x in range(w):
            if grid[y][x] == 1 and biome_grid[y][x] == "":
                neigh = []
                for dx, dy in ((1,0),(-1,0),(0,1),(0,-1)):
                    nx, ny = x+dx, y+dy
                    if _in_bounds(nx, ny, w, h) and biome_grid[ny][nx] != "":
                        neigh.append(biome_grid[ny][nx])
                biome_grid[y][x] = neigh[0] if neigh else biome_names[0]
    return biome_grid

def _region_bbox(cells: List[Tuple[int, int]]) -> Tuple[int, int, int, int]:
    xs = [c[0] for c in cells]; ys = [c[1] for c in cells]
    return (min(xs), min(ys), max(xs), max(ys))

def _approx_exits(grid: List[List[Cell]], cells: List[Tuple[int, int]]) -> int:
    # Roughly: count boundary floor cells adjacent to wall in 4-neighborhood
    h = len(grid); w = len(grid[0])
    exits = 0
    cellset = set(cells)
    for x, y in cells:
        boundary = False
        for dx, dy in ((1,0),(-1,0),(0,1),(0,-1)):
            nx, ny = x+dx, y+dy
            if not _in_bounds(nx, ny, w, h) or grid[ny][nx] == 0:
                boundary = True
        if boundary:
            exits += 1
    # normalize: exits in "connection-ish" units
    return max(1, exits // 20)

def _classify_region(cells: List[Tuple[int, int]], bbox: Tuple[int,int,int,int]) -> str:
    size = len(cells)
    x0, y0, x1, y1 = bbox
    bw = x1 - x0 + 1
    bh = y1 - y0 + 1
    aspect = (bw / bh) if bh else 1.0
    fill_ratio = size / max(1, (bw * bh))

    # Heuristics:
    if size < 80:
        return "pocket"
    if fill_ratio > 0.55 and (bw > 12 and bh > 12):
        return "chamber"
    if fill_ratio < 0.35 and (aspect > 2.0 or aspect < 0.5):
        return "tunnel"
    return "cavern"

def _name_region(rng: random.Random, kind: str, biome: str, idx: int) -> str:
    adjectives = {
        "Limestone": ["Pale", "Chalk", "Echoing", "Ancient", "Sighing"],
        "Fungal": ["Spore", "Mossy", "Bluecap", "Breathing", "Lantern"],
        "Crystal": ["Gleaming", "Shard", "Prismatic", "Glass", "Singing"],
        "Flooded": ["Drowned", "Dripping", "Blackwater", "Tide", "Cold"],
        "Volcanic": ["Cinder", "Soot", "Ashen", "Ember", "Basalt"],
        "Bonefield": ["Pale", "Rattle", "Hollow", "Skull", "Grave"],
        "Slime": ["Viscous", "Ooze", "Seeping", "Grease", "Glaze"],
        "Ruins": ["Worked", "Broken", "Carved", "Forgotten", "Sealed"],
    }.get(biome, ["Strange", "Quiet", "Old", "Deep"])

    nouns = {
        "chamber": ["Hall", "Vault", "Bowl", "Cathedral", "Rotunda"],
        "tunnel": ["Run", "Wormway", "Pass", "Crawl", "Vein"],
        "cavern": ["Grotto", "Cave", "Warren", "Hollow", "Maze"],
        "pocket": ["Niche", "Pocket", "Den", "Cell", "Cubby"],
    }.get(kind, ["Cave"])

    return f"{rng.choice(adjectives)} {rng.choice(nouns)} #{idx}"

def _build_regions(grid: List[List[Cell]], biome_grid: List[List[str]], rng: random.Random) -> List[CavernRegion]:
    floor_regions = _regions_of_type(grid, 1)
    regions: List[CavernRegion] = []
    rid = 1
    for cells in sorted(floor_regions, key=len, reverse=True):
        bbox = _region_bbox(cells)
        kind = _classify_region(cells, bbox)
        exits = _approx_exits(grid, cells)

        # biome: majority vote
        counts: Dict[str, int] = {}
        for x, y in cells:
            b = biome_grid[y][x]
            counts[b] = counts.get(b, 0) + 1
        biome = max(counts.keys(), key=lambda k: counts[k]) if counts else "Limestone"

        name = _name_region(rng, kind, biome, rid)
        regions.append(CavernRegion(
            id=rid,
            cells=cells,
            bbox=bbox,
            size=len(cells),
            kind=kind,
            exits=exits,
            name=name,
            biome=biome
        ))
        rid += 1
    return regions

def _stats(grid: List[List[Cell]], regions: List[CavernRegion]) -> Dict[str, float]:
    h = len(grid); w = len(grid[0])
    floors = sum(1 for y in range(h) for x in range(w) if grid[y][x] == 1)
    walls = (w * h) - floors
    return {
        "width": float(w),
        "height": float(h),
        "floor_cells": float(floors),
        "wall_cells": float(walls),
        "floor_ratio": float(floors / max(1, w*h)),
        "region_count": float(len(regions)),
        "largest_region": float(max((r.size for r in regions), default=0)),
    }

# ---------- Public API ----------

def generate_cavern(params: CavernParams, rng: random.Random, seed_used: int) -> CavernResult:
    grid = _init_grid(params, rng)
    for _ in range(params.smooth_steps):
        grid = _smooth(grid, params)

    if params.close_small_holes:
        _close_tiny_holes(grid)

    if params.keep_largest_region:
        _keep_largest_floor_region(grid)

    _remove_small_regions(grid, target=1, min_size=params.min_region_size)

    if params.widen_passes > 0:
        _widen(grid, params.widen_passes)

    biome_grid = _biome_spread(grid, rng, params) if params.biome_mode == "simple" else [["" for _ in range(params.width)] for _ in range(params.height)]
    regions = _build_regions(grid, biome_grid, rng)
    return CavernResult(
        width=params.width,
        height=params.height,
        grid=grid,
        seed=seed_used,
        regions=regions,
        biome_grid=biome_grid,
        stats=_stats(grid, regions),
    )