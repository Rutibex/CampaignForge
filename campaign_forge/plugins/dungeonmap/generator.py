from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict
import random
import math

from .contents import RoomContents, generate_room_contents, random_lock

Point = Tuple[int, int]  # (x,y)

@dataclass
class Door:
    x: int
    y: int
    orientation: str  # "H" or "V"
    secret: bool = False
    # Extended door semantics (kept backward-compatible)
    door_type: str = "wooden"  # wooden/stone/iron/portcullis/magical/organic/illusory
    state: str = "closed"      # open/closed/locked/jammed/trapped/broken/barricaded
    locked: bool = False
    lock_type: str = ""
    trapped: bool = False
    trap_desc: str = ""
    notes: str = ""

@dataclass
class Room:
    id: int
    x: int
    y: int
    w: int
    h: int
    tag: str = "empty"
    locked: bool = False
    lock_type: str = ""
    # Room semantics + metadata (new; defaults keep old projects safe)
    name: str = ""
    function: str = ""
    condition: str = ""
    occupancy: str = ""
    control: str = ""
    description: str = ""
    gm_notes: str = ""
    linked_scratchpad_ids: List[str] = field(default_factory=list)
    contents: RoomContents = field(default_factory=RoomContents)

    @property
    def center(self) -> Point:
        return (self.x + self.w // 2, self.y + self.h // 2)

    def contains_cell(self, cx: int, cy: int) -> bool:
        return self.x <= cx < self.x + self.w and self.y <= cy < self.y + self.h

@dataclass
class Corridor:
    points: List[Point]  # polyline (Manhattan segments)
    secret: bool = False

@dataclass
class Dungeon:
    width: int
    height: int
    rooms: List[Room]
    corridors: List[Corridor]
    doors: List[Door]
    grid: List[List[int]]  # 0 wall, 1 floor

@dataclass
class DungeonGenConfig:
    width: int = 80
    height: int = 60
    room_attempts: int = 140
    room_min_size: int = 5
    room_max_size: int = 14
    max_rooms: int = 18
    corridor_width: int = 1
    straightness: float = 0.65        # 0..1 higher=more L-shaped clean
    corridor_density: float = 0.35    # 0..1 extra loops/connections
    dead_end_prune: float = 0.25      # 0..1 remove some dead ends
    cave_mode: bool = False           # if True: carve caves behind corridors
    cave_fill: float = 0.46           # initial wall fill probability for cave
    cave_steps: int = 4               # cellular automata smoothing
    secret_doors: int = 2
    secret_corridors: int = 1
    danger: int = 3                   # affects contents
    seed: Optional[int] = None


ROOM_TAGS = [
    "empty","lair","shrine","treasury","workshop","library","prison","guardpost",
    "crypt","laboratory","armory","messhall","portal","well","nursery","throne"
]

def _rects_intersect(a: Room, b: Room, padding: int = 1) -> bool:
    ax1, ay1 = a.x - padding, a.y - padding
    ax2, ay2 = a.x + a.w + padding, a.y + a.h + padding
    bx1, by1 = b.x - padding, b.y - padding
    bx2, by2 = b.x + b.w + padding, b.y + b.h + padding
    return not (ax2 <= bx1 or bx2 <= ax1 or ay2 <= by1 or by2 <= ay1)

def _carve_room(grid: List[List[int]], r: Room) -> None:
    for y in range(r.y, r.y + r.h):
        for x in range(r.x, r.x + r.w):
            grid[y][x] = 1

def _carve_corridor(grid: List[List[int]], pts: List[Point], width: int = 1) -> None:
    def carve_cell(cx: int, cy: int) -> None:
        half = width // 2
        for dy in range(-half, half + 1):
            for dx in range(-half, half + 1):
                x = cx + dx
                y = cy + dy
                if 0 <= y < len(grid) and 0 <= x < len(grid[0]):
                    grid[y][x] = 1

    for i in range(len(pts) - 1):
        x1, y1 = pts[i]
        x2, y2 = pts[i + 1]
        x, y = x1, y1
        carve_cell(x, y)
        while x != x2 or y != y2:
            if x < x2:
                x += 1
            elif x > x2:
                x -= 1
            elif y < y2:
                y += 1
            elif y > y2:
                y -= 1
            carve_cell(x, y)

def _l_or_jog_path(rng: random.Random, a: Point, b: Point, straightness: float) -> List[Point]:
    ax, ay = a
    bx, by = b
    if rng.random() < straightness:
        if rng.random() < 0.5:
            return [(ax, ay), (bx, ay), (bx, by)]
        return [(ax, ay), (ax, by), (bx, by)]

    # Jog: 1-2 bends
    pts: List[Point] = [(ax, ay)]
    midx = rng.randint(min(ax, bx), max(ax, bx))
    midy = rng.randint(min(ay, by), max(ay, by))
    if rng.random() < 0.5:
        pts += [(midx, ay), (midx, midy), (bx, midy)]
    else:
        pts += [(ax, midy), (midx, midy), (midx, by)]
    pts.append((bx, by))
    cleaned = [pts[0]]
    for p in pts[1:]:
        if p != cleaned[-1]:
            cleaned.append(p)
    return cleaned

def _neighbors4(x: int, y: int) -> List[Point]:
    return [(x+1,y),(x-1,y),(x,y+1),(x,y-1)]

def _degree_floor(grid: List[List[int]], x: int, y: int) -> int:
    deg = 0
    for nx, ny in _neighbors4(x,y):
        if 0 <= ny < len(grid) and 0 <= nx < len(grid[0]) and grid[ny][nx] == 1:
            deg += 1
    return deg

def _prune_dead_ends(rng: random.Random, grid: List[List[int]], amount: float) -> None:
    """
    Removes a fraction of dead-end corridor cells (degree==1) by turning them into walls.
    Not perfect (doesn't distinguish rooms), but good "donjon-ish" feel.
    """
    if amount <= 0:
        return

    candidates: List[Point] = []
    h = len(grid); w = len(grid[0])
    for y in range(1, h-1):
        for x in range(1, w-1):
            if grid[y][x] == 1 and _degree_floor(grid, x, y) == 1:
                candidates.append((x,y))

    rng.shuffle(candidates)
    target = int(len(candidates) * amount)

    removed = 0
    for x,y in candidates:
        if removed >= target:
            break
        # Re-check; changes propagate
        if grid[y][x] == 1 and _degree_floor(grid, x, y) == 1:
            grid[y][x] = 0
            removed += 1

def _cave_carve(rng: random.Random, width: int, height: int, fill: float, steps: int) -> List[List[int]]:
    """
    Cellular automata cave; returns grid with 1=floor,0=wall (inverted from fill)
    We'll merge it behind the main dungeon to get "cave mode" vibes.
    """
    g = [[0 for _ in range(width)] for _ in range(height)]
    for y in range(height):
        for x in range(width):
            if x == 0 or y == 0 or x == width-1 or y == height-1:
                g[y][x] = 0
            else:
                g[y][x] = 0 if rng.random() < fill else 1  # more walls when fill high

    def count_walls(x: int, y: int) -> int:
        c = 0
        for yy in range(y-1, y+2):
            for xx in range(x-1, x+2):
                if xx == x and yy == y:
                    continue
                if xx < 0 or yy < 0 or xx >= width or yy >= height:
                    c += 1
                elif g[yy][xx] == 0:
                    c += 1
        return c

    for _ in range(steps):
        ng = [[g[y][x] for x in range(width)] for y in range(height)]
        for y in range(1, height-1):
            for x in range(1, width-1):
                walls = count_walls(x,y)
                # classic cave rules
                if walls >= 5:
                    ng[y][x] = 0
                else:
                    ng[y][x] = 1
        g = ng
    return g

def _merge_cave(base: List[List[int]], cave: List[List[int]], blend: float = 0.55) -> None:
    """
    Merge some cave floors into base walls (never erase existing floors).
    """
    h = len(base); w = len(base[0])
    for y in range(1, h-1):
        for x in range(1, w-1):
            if base[y][x] == 0 and cave[y][x] == 1:
                # Blend chance happens outside this function if desired
                base[y][x] = 1

def _place_doors(rng: random.Random, d: Dungeon) -> List[Door]:
    """
    Place doors where a corridor meets a room boundary.
    Door symbol orientation is based on the local wall direction.
    """
    doors: Dict[Tuple[int,int], Door] = {}
    grid = d.grid

    # Helper: determine if cell is on room boundary and adjacent to corridor
    for room in d.rooms:
        # scan perimeter cells just inside room and find adjacency to outside floors
        for y in range(room.y, room.y + room.h):
            for x in range(room.x, room.x + room.w):
                # only perimeter
                if not (x == room.x or x == room.x + room.w - 1 or y == room.y or y == room.y + room.h - 1):
                    continue

                if grid[y][x] != 1:
                    continue

                # check outside neighbors for floor (corridor)
                for nx, ny in _neighbors4(x,y):
                    if not (0 <= ny < d.height and 0 <= nx < d.width):
                        continue
                    if room.contains_cell(nx, ny):
                        continue
                    if grid[ny][nx] == 1:
                        # Door goes on boundary cell (x,y)
                        # Orientation: if neighbor is left/right -> vertical door, else horizontal door
                        orientation = "V" if nx != x else "H"
                        key = (x,y)
                        if key not in doors:
                            doors[key] = Door(x=x, y=y, orientation=orientation)
    return list(doors.values())

def _place_secrets(rng: random.Random, d: Dungeon, secret_doors: int, secret_corridors: int) -> None:
    # Secret doors: convert some existing doors
    if d.doors and secret_doors > 0:
        rng.shuffle(d.doors)
        for door in d.doors[:min(secret_doors, len(d.doors))]:
            door.secret = True

    # Secret corridors: add some extra corridors flagged secret (carved in grid, but you draw dashed)
    rooms = d.rooms
    for _ in range(max(0, secret_corridors)):
        if len(rooms) < 2:
            break
        a = rng.choice(rooms).center
        b = rng.choice(rooms).center
        if a == b:
            continue
        pts = _l_or_jog_path(rng, a, b, straightness=0.35)  # more twisty
        _carve_corridor(d.grid, pts, width=1)
        d.corridors.append(Corridor(points=pts, secret=True))

def _assign_contents(rng: random.Random, rooms: List[Room], danger: int) -> None:
    for r in rooms:
        r.contents = generate_room_contents(rng, danger=danger)
        # Randomly lock some rooms
        if rng.random() < min(0.35, 0.10 + danger * 0.03):
            r.locked = True
            r.lock_type = random_lock(rng)

def generate_dungeon(cfg: DungeonGenConfig) -> Dungeon:
    rng = random.Random(cfg.seed) if cfg.seed is not None else random.Random()

    grid = [[0 for _ in range(cfg.width)] for _ in range(cfg.height)]
    rooms: List[Room] = []

    # Place rooms
    for _ in range(cfg.room_attempts):
        if len(rooms) >= cfg.max_rooms:
            break
        w = rng.randint(cfg.room_min_size, cfg.room_max_size)
        h = rng.randint(cfg.room_min_size, cfg.room_max_size)
        x = rng.randint(1, cfg.width - w - 2)
        y = rng.randint(1, cfg.height - h - 2)

        candidate = Room(id=len(rooms) + 1, x=x, y=y, w=w, h=h)
        if any(_rects_intersect(candidate, r, padding=1) for r in rooms):
            continue

        candidate.tag = rng.choice(ROOM_TAGS)
        rooms.append(candidate)
        _carve_room(grid, candidate)

    corridors: List[Corridor] = []

    # Connect rooms
    if rooms:
        ordered = sorted(rooms, key=lambda rr: (rr.center[0], rr.center[1]))
        # base chain ensures connectivity
        for i in range(1, len(ordered)):
            a = ordered[i - 1].center
            b = ordered[i].center
            pts = _l_or_jog_path(rng, a, b, cfg.straightness)
            _carve_corridor(grid, pts, width=cfg.corridor_width)
            corridors.append(Corridor(points=pts, secret=False))

        # corridor density: extra loops
        possible = max(0, len(rooms) * (len(rooms)-1) // 2 - (len(rooms)-1))
        extra = int((len(rooms) * cfg.corridor_density) + rng.random() * 2.0)
        extra = max(0, min(extra, max(1, possible // 6) if possible > 0 else extra))

        for _ in range(extra):
            ra = rng.choice(rooms).center
            rb = rng.choice(rooms).center
            if ra == rb:
                continue
            pts = _l_or_jog_path(rng, ra, rb, cfg.straightness)
            _carve_corridor(grid, pts, width=cfg.corridor_width)
            corridors.append(Corridor(points=pts, secret=False))

    # Cave mode (blend caves behind corridors/rooms)
    if cfg.cave_mode:
        cave = _cave_carve(rng, cfg.width, cfg.height, fill=cfg.cave_fill, steps=cfg.cave_steps)
        # Merge cave floors into walls only (never erase floors)
        for y in range(1, cfg.height-1):
            for x in range(1, cfg.width-1):
                if grid[y][x] == 0 and cave[y][x] == 1 and rng.random() < 0.55:
                    grid[y][x] = 1

    # Dead end pruning
    _prune_dead_ends(rng, grid, cfg.dead_end_prune)

    d = Dungeon(
        width=cfg.width,
        height=cfg.height,
        rooms=rooms,
        corridors=corridors,
        doors=[],
        grid=grid
    )

    # Doors + secrets + contents
    d.doors = _place_doors(rng, d)
    _place_secrets(rng, d, cfg.secret_doors, cfg.secret_corridors)
    _assign_contents(rng, d.rooms, cfg.danger)

    return d


def _rooms_from(d_or_rooms):
    """Accept either a Dungeon or a list of Room for backward compatibility."""
    if d_or_rooms is None:
        return []
    # Duck-typing: Dungeon-like
    if hasattr(d_or_rooms, "rooms"):
        return list(getattr(d_or_rooms, "rooms") or [])
    # Already a list/iterable of rooms
    if isinstance(d_or_rooms, list):
        return d_or_rooms
    try:
        return list(d_or_rooms)
    except Exception:
        return []

def dungeon_room_key(d_or_rooms) -> str:
    lines = []
    rooms = _rooms_from(d_or_rooms)
    for r in sorted(rooms, key=lambda rr: rr.id):
        lock = f" LOCKED ({r.lock_type})" if getattr(r, "locked", False) else ""
        tag = getattr(r, "tag", "Room")
        w = getattr(r, "w", 0)
        h = getattr(r, "h", 0)
        x = getattr(r, "x", 0)
        y = getattr(r, "y", 0)
        lines.append(f"Room {r.id:02d}: {tag}{lock} ({w}x{h}) @ ({x},{y})")
    return "\n".join(lines) if lines else "(No rooms generated)"

def dungeon_contents_text(d_or_rooms) -> str:
    lines = []
    rooms = _rooms_from(d_or_rooms)
    for r in sorted(rooms, key=lambda rr: rr.id):
        c = getattr(r, "contents", None)
        lines.append(f"## Room {r.id:02d}: {getattr(r, 'tag', 'Room')}")
        # Semantics
        fn = getattr(r, 'function', None)
        cond = getattr(r, 'condition', None)
        occ = getattr(r, 'occupancy', None)
        ctrl = getattr(r, 'control', None)
        meta_bits = [b for b in [fn, cond, occ, ctrl] if b]
        if meta_bits:
            lines.append(f"*Semantics:* {', '.join(meta_bits)}")
        if getattr(r, 'locked', False):
            lines.append(f"- **Locked:** {getattr(r,'lock_type','lock')}")
        if c is not None:
            if getattr(c, 'encounter', None):
                lines.append(f"- **Encounter:** {c.encounter}")
            if getattr(c, 'trap', None):
                lines.append(f"- **Trap:** {c.trap}")
            if getattr(c, 'treasure', None):
                lines.append(f"- **Treasure:** {c.treasure}")
            if getattr(c, 'notes', None):
                lines.append(f"- **Notes:** {c.notes}")
        if (c is None) or not (getattr(c,'encounter',None) or getattr(c,'trap',None) or getattr(c,'treasure',None) or getattr(c,'notes',None) or getattr(r,'locked',False)):
            lines.append("- (empty)")
        lines.append("")
    return "\n".join(lines).rstrip() if lines else "(No rooms generated)"

