
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
import random

# Emit a real dungeon layout by reusing Campaign Forge's existing dungeon-map
# data structures. This lets us render and export maps without reinventing the wheel.
from campaign_forge.plugins.dungeonmap.generator import (
    Dungeon as MapDungeon,
    Room as MapRoom,
    Corridor as MapCorridor,
    Door as MapDoor,
)

# ----------------------------
# Utilities
# ----------------------------

def d(rng: random.Random, sides: int) -> int:
    return rng.randint(1, sides)

def clamp(n: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, n))

def choose(rng: random.Random, items: List[str]) -> str:
    return items[rng.randrange(0, len(items))]

# ----------------------------
# Room Type Tables (Depth-based)
# ----------------------------

@dataclass
class DepthBand:
    name: str
    # each entry: (low, high, room_type)
    ranges: List[Tuple[int, int, str]]

DEPTH_BANDS: List[DepthBand] = [
    DepthBand("0-10", [
        (1, 34, "Normal"),
        (35, 66, "Special"),
        (67, 86, "Rare"),
        (87, 97, "Unique"),
        (98, 99, "Legendary"),
        (100, 100, "Epic"),
    ]),
    DepthBand("11-20", [
        (1, 29, "Normal"),
        (30, 59, "Special"),
        (60, 75, "Rare"),
        (76, 94, "Unique"),
        (95, 98, "Legendary"),
        (99, 100, "Epic"),
    ]),
    DepthBand("21-30", [
        (1, 24, "Normal"),
        (25, 39, "Special"),
        (40, 69, "Rare"),
        (70, 93, "Unique"),
        (94, 96, "Legendary"),
        (97, 100, "Epic"),
    ]),
    DepthBand("31-40", [
        (1, 9, "Normal"),
        (10, 29, "Special"),
        (30, 49, "Rare"),
        (50, 92, "Unique"),
        (93, 96, "Legendary"),
        (97, 100, "Epic"),
    ]),
    DepthBand("41+", [
        (1, 1, "Normal"),
        (2, 19, "Special"),
        (20, 39, "Rare"),
        (40, 79, "Unique"),
        (80, 89, "Legendary"),
        (90, 100, "Epic"),
    ]),
]

def pick_depth_band(depth: int) -> DepthBand:
    if depth <= 10:
        return DEPTH_BANDS[0]
    if depth <= 20:
        return DEPTH_BANDS[1]
    if depth <= 30:
        return DEPTH_BANDS[2]
    if depth <= 40:
        return DEPTH_BANDS[3]
    return DEPTH_BANDS[4]

def roll_room_type(rng: random.Random, depth: int) -> str:
    band = pick_depth_band(depth)
    roll = d(rng, 100)
    for lo, hi, rt in band.ranges:
        if lo <= roll <= hi:
            return rt
    return "Normal"

# ----------------------------
# Normal Room Generator Tables
# ----------------------------

MAIN_PASSAGE = [
    (1, 2, "Continue Straight (roll again in 30')"),
    (3, 5, "Door"),
    (6, 10, "Side Passage(s)"),
    (11, 13, "Passage Turn"),
    (14, 16, "Room"),
    (17, 17, "Passage End"),
    (18, 18, "Tricks and Traps"),
    (19, 19, "Monster Encounters"),
    (20, 20, "Other Encounters"),
]

DOORS = [
    "Left", "Right", "Ahead", "Above", "Below",
    "Hidden door on the left", "Hidden door on the right", "Hidden door ahead",
    "Secret door above", "Secret door below",
    "Double doors on the left", "Double doors on the right", "Double doors ahead",
    "Trapdoor on the left", "Trapdoor on the right",
    "Locked door ahead", "Portcullis above", "Broken door below",
    "Magical portal on the left", "Sealed door ahead",
]

SIDE_PASSAGES = [
    (1, 10, "One Passage"),
    (11, 18, "Two Passages"),
    (19, 19, "Three Passages"),
    (20, 20, "Four Passages"),
]

PASSAGE_ANGLE = [
    (1, 2, "45° right"),
    (3, 8, "90° right"),
    (9, 10, "135° right"),
    (11, 12, "45° left"),
    (13, 18, "90° left"),
    (19, 20, "135° left"),
]

PASSAGE_PROPERTIES = [
    "1' wide — incredibly narrow, hard for bulky gear or large creatures.",
    "5' wide — standard corridor.",
    "5' wide — walls carved with ancient legends and forgotten lore.",
    "10' wide — thick mist limits vision to a few feet.",
    "10' wide — gradual upward slope toward a hidden high chamber.",
    "10' wide — shelves of dusty tomes and fragile scrolls (ruined library).",
    "10' wide — phosphorescent mushrooms cast eerie light.",
    "10' wide — rushing water echoes nearby (underground stream).",
    "10' wide — ceiling so low tall folk must crouch/crawl.",
    "10' wide — corridor splits into two paths.",
    "10' wide — floor coated in slippery slime.",
    "10' wide — ancient runes; touching triggers enchantment or trap.",
    "10' wide — bats swarm and distract.",
    "20' wide — built for large creatures or marching groups.",
    "20' wide — mosaic floor maps the surrounding dungeon (clue!).",
    "20' wide — ornate statues of deities and mythic beasts.",
    "30' wide — grand chamber-like corridor with relic alcoves.",
    "30' wide — epic tapestries depict heroic battles.",
    "50' wide — colossal thoroughfare; awe-inspiring scale.",
    "Special — magically shifting maze corridor; reroutes itself.",
]

SPECIAL_PASSAGES = [
    "10' Stream — clear and drinkable.",
    "10' Stream — murky, predator-filled water.",
    "10' Stream — splits; choose the correct branch.",
    "10' Stream — vanishes into a hole; leaves a dry mystery channel.",
    "10' Stream — small waterfall; soothing, loud.",
    "10' Stream — defies gravity, flowing along the ceiling.",
    "10' Stream — widens into a reflective pond.",
    "10' Stream — rickety bridge spans it.",
    "10' Stream — electrified; crackling arcs.",
    "10' Stream — floating treasure chests tempt risk.",
    "20' Chasm — darkness below; needs bridge or leap.",
    "20' Chasm — filled with poisonous mist.",
    "20' Chasm — flying denizens harry crossers.",
    "20' Lava Stream — intense heat; protection required.",
    "20' Lava Stream — splits into channels; navigational hazard.",
    "Shrinking hallway — narrows to 1' over distance.",
    "30' Pneumatic tube — one-way forward.",
    "30' Pneumatic tube — one-way backward.",
    "60' River — fast and deep; boat/strong swimmer.",
    "60' River — plunges into huge waterfall; roaring mist.",
]

ROOMS = [
    "Square 10'×10'",
    "Square 10'×10' with a hidden alcove",
    "Square 20'×20'",
    "Square 20'×20' with an off-center column",
    "Square 30'×30'",
    "Square 30'×30' with a 30' ceiling",
    "Square 40'×40'",
    "Square 40'×40' with a statue or central feature",
    "Rectangle 10'×20'",
    "Rectangle 10'×20' with pit or elevated platform",
    "Rectangle 10'×30'",
    "Rectangle 10'×30' with multiple levels/mezzanine",
    "Rectangle 10'×40'",
    "Rectangle 10'×40' bisected by a river/chasm",
    "Rectangle 20'×40'",
    "Rectangle 20'×40' with skylight or ceiling mural",
    "Special Shape + Special Size",
    "Special Shape + Special Size",
    "Special Shape + Special Size",
    "Special Shape + Special Size",
]

SPECIAL_SHAPES = [
    (1, 2, "Triangle"),
    (3, 4, "Circle"),
    (5, 6, "Oval"),
    (7, 8, "Hexagon"),
    (9, 10, "Star"),
    (11, 12, "Cave"),
    (13, 14, "Free-hand"),
    (15, 15, "Spiral"),
    (16, 16, "Diamond"),
    (17, 17, "L-Shape"),
    (18, 18, "Cross"),
    (19, 19, "Octagon"),
    (20, 20, "Crescent"),
]

SPECIAL_SIZE = [
    (1, 1, "50 sq ft (small storage)"),
    (2, 3, "100 sq ft (small bedroom)"),
    (4, 5, "300 sq ft (study/workshop)"),
    (6, 7, "500 sq ft (medium common room)"),
    (8, 9, "700 sq ft (large bedroom/small common room)"),
    (10, 11, "900 sq ft (large common room)"),
    (12, 13, "1,100 sq ft (banquet/large workshop)"),
    (14, 15, "1,300 sq ft (small ballroom/throne room)"),
    (16, 17, "1,500 sq ft (medium ballroom/large throne)"),
    (18, 18, "2,000 sq ft (large feast hall)"),
    (19, 19, "3,000 sq ft (grand royal chamber)"),
    (20, 20, "10,000 sq ft (great hall/cavernous)"),
]

EXITS = [
    (1, 3, "Left"),
    (4, 6, "Left and Straight"),
    (7, 8, "Left and Right"),
    (9, 11, "Right"),
    (12, 14, "Right and Straight"),
    (15, 16, "Right and Left"),
    (17, 18, "Straight"),
    (19, 19, "Straight and Left"),
    (20, 20, "Roll Twice"),
]

ROOM_CONTAINS = [
    (1, 8, "Remnants of the Past"),
    (9, 10, "Monsters"),
    (11, 12, "Treasures"),
    (13, 15, "Tricks and Traps"),
    (16, 17, "Other Encounters"),
    (18, 20, "Roll Twice"),
]

TREASURES = [
    (1, 12, "Mundane Items"),
    (13, 17, "Food"),
    (18, 18, "Magical Items"),
    (19, 19, "Fantastic Items"),
    (20, 20, "Major Treasures"),
]

TREASURE_CONTAINER = [
    (1, 10, "Chests"),
    (11, 14, "Pots"),
    (15, 16, "Bags"),
    (17, 17, "Urns"),
    (18, 18, "A hollow statue"),
    (19, 19, "Loose on the ground"),
    (20, 20, "In a monster"),
]

TREASURE_TRAP = [
    (1, 6, "Contact poison"),
    (7, 11, "Poisoned needles"),
    (12, 13, "Poison gas"),
    (14, 15, "Sleeping gas"),
    (16, 16, "Explosives"),
    (17, 17, "Acid dissolves contents"),
    (18, 18, "Ink bomb"),
    (19, 19, "Blade trap"),
    (20, 20, "Net trap"),
]

TREASURE_CONCEALMENT = [
    (1, 8, "Disguised as something else"),
    (9, 10, "Dirty and smelly"),
    (11, 12, "Invisible"),
    (13, 15, "Intangible"),
    (16, 19, "Illusions of monsters"),
    (20, 20, "A strict accountant catalogued it"),
]

MUNDANE_ITEMS = [
    "Rusty key","Torn map fragment","Broken pocket watch","Strange-looking rock","Empty potion bottle",
    "Tangled rope","Bent iron spike","Moldy spellbook","Cracked mirror","Weathered playing cards",
    "Patched leather gloves","Chipped ceramic mug","Dented brass compass","Frayed backpack","Faded tapestry scrap",
    "Rusted dagger","Tattered cloak","Wax-sealed letter (unreadable)","Half-burned candle","Shattered hourglass",
]

FOOD = [
    "Dried beef jerky","Hardtack","Salted fish","Dried apples","Smoked sausages","Honeycomb","Roasted nuts",
    "Pickled vegetables","Smoked cheese","Preserved olives","Salted pork rinds","Sourdough bread","Dried apricots",
    "Cured meats","Spicy dried mango","Preserved eggs","Smoked oysters","Sunflower seeds","Pickled herring","Dried dates",
]

MAGIC_ITEMS = [
    "Amulet of Elemental Command","Bag of Holding","Boots of Elvenkind","Cloak of Invisibility","Deck of Many Things",
    "Eversmoking Bottle","Flame Tongue","Gloves of Missile Snaring","Helm of Telepathy","Lantern of Revealing",
    "Medallion of Thoughts","Ring of Feather Falling","Rod of Absorption","Scarab of Protection","Sending Stones",
    "Staff of Healing","Tome of Knowledge","Wand of Polymorph","Whip of Warning","Yew Wand",
]

FANTASTIC_ITEMS = [
    "Potion of Bubble Breath","Cursed Ring of Politeness","Feathered Hat of Levitation","Glove of Ever‑Changing Colors",
    "Pocket Mirror of Self‑Reflection","Boots of the Silent Jester","Crystal Ball of Lost Memories","Everburning Candlestick",
    "Coinpurse of Charity","Ring of the Chatterbox","Goblet of Bottomless Thirst","Quill of Endless Scribbles",
    "Whistle of the Enigmatic Echo","Pendant of Featherfall","Dice of Fortune","Mask of Many Faces",
    "Lantern of Hushed Whispers","Scarf of Elemental Resistance","Book of Lost Languages","Keyring of Unexpected Locks",
]

MAJOR_TREASURES = [
    "Copper coins (1d1000)","Silver coins (1d1000)","Electrum coins (1d500)","Gold coins (1d1000)","Platinum coins (1d500)",
    "Gemstones (2d10, 10–100 gp each)","Jewelry (1d6, 100–1000 gp each)","Minor magic item (your table)",
    "Major magic item (Uncommon)","Small chest of mixed coins (1d500 cp/sp/gp)",
    "Large chest mixed coins (1d1000 cp/sp/gp + 1d500 pp)","Fine artwork (1d4, 250–2500 gp)","Major magic item (Rare)",
    "Potion collection (1d6)","Scroll collection (1d6)","Bag of Holding (2d10×100 gp + 1d6 minor items)",
    "Major magic item (Very Rare)","Dragon hoard (gp/pp/gems/jewelry + major item)","Spellbook (1d6+4 spells 1–3)",
    "Major magic item (Legendary)",
]

TRICKS_TRAPS = [
    "Secret door (DC 15 Perception) — shortcut or stash.",
    "Gas trap (Con DC 12) — 2d6 poison in 10' radius.",
    "Pit trap (Dex DC 13) — fall for 1d6 bludgeoning.",
    "Oil slick (Dex DC 14) — prone; fire ignites for 2d6.",
    "Net trap (Dex DC 12) — restrained; escape Str DC 15.",
    "Swinging blades (Dex DC 15) — 3d6 slashing.",
    "Illusionary wall (Investigation DC 16) — waste time/resources.",
    "Illusionary monster (Wis DC 15) — 2d8 psychic backlash.",
    "Poison needle plate (Dex DC 13) — 1d8 + poisoned 1 min.",
    "Falling chandelier (Dex DC 14) — 2d6 bludgeoning.",
    "Acid spray (Dex DC 15) — 3d6 acid cone.",
    "Teleport glyph (Cha DC 16) — party separated.",
    "Falling rocks (Dex DC 12) — 2d4 bludgeoning.",
    "Web trap (Str DC 13) — restrained.",
    "Poison darts (Dex DC 14) — 1d10 + poisoned 1 min.",
    "Flamethrower line (Dex DC 16) — 3d8 fire.",
    "Crushing ceiling (Dex DC 15) — 4d6 bludgeoning.",
    "Wild magic glyph (roll 1d6) — fireball / lightning / sleep.",
    "Falling floor tiles (Dex DC 14) — drop for 2d6.",
    "Mimic chest — +6 to hit, 2d8+4 bite; grapple risk.",
]

OTHER_ENCOUNTERS = [
    "Lost explorer — disoriented, seeking guidance.",
    "Mysterious merchant — exotic goods and odd bargains.",
    "Friendly fey — riddles, trinkets, mischief.",
    "Wise hermit — cryptic clue, deep lore.",
    "Trapped spirit — unfinished business; offers info.",
    "Lost pet — harmless creature needing rescue.",
    "Enigmatic bard — tale hides a secret.",
    "Injured scout — knows layout/dangers.",
    "Potion mishap — alchemist needs help.",
    "Archaeologist — wants aid retrieving relic info.",
    "Fortune teller — prophecy or warning.",
    "Friendly goblin — hidden routes and tribal secrets.",
    "Linguistics expert — deciphers inscriptions.",
    "Resourceful engineer — repairs mechanisms; gifts gadgets.",
    "Starving prisoner — desperate; knows secrets.",
    "Sculptor — makes art from dungeon debris; sees patterns.",
    "Lost love — searching; reward for reunion.",
    "Cursed soul — needs specific task/object to break hex.",
    "Singing siren — boon or temptation.",
    "Goblin market — trade stolen oddities for favors.",
]

# ----------------------------
# Creative layer: "Mods" synthesizer (1-600)
# ----------------------------

MOD_ADJECTIVES = [
    "Fractal", "Gilded", "Sanguine", "Ossified", "Clockwork", "Murmuring", "Star‑salted", "Moss‑choked",
    "Mirror‑bright", "Hollow", "Resonant", "Gravitic", "Salt‑slick", "Thorned", "Ashen", "Luminous",
    "Ink‑stained", "Frost‑rimmed", "Vein‑lit", "Ceremonial", "Votive", "Spore‑fogged", "Rust‑hymning",
    "Siren‑haunted", "Rune‑stitched", "Lantern‑sewn", "Chorus‑echoing", "Glacier‑cold", "Cinder‑warm",
]

MOD_NOUNS = [
    "sigils", "altars", "chains", "mirrors", "basins", "statues", "tapestries", "bones", "mushrooms", "pipes",
    "gargoyles", "glyphs", "masks", "thrones", "keys", "bells", "urns", "doors", "grates", "candles",
    "roots", "cables", "coins", "wells", "scrolls", "shadows", "veins", "clocks", "vents", "pylons",
]

MOD_TWISTS = [
    "time runs oddly here (+/− 10 minutes each room).",
    "whispers answer questions, but demand a secret in return.",
    "gravity leans 15° toward the nearest exit.",
    "all flames burn blue; cold damage is empowered.",
    "blood stains crawl toward hidden doors.",
    "metal sweats rust; weapons degrade unless oiled.",
    "echoes repeat your last lie instead of your last word.",
    "shadows detach and lag behind their owners.",
    "footprints appear *before* you step.",
    "water flows uphill toward treasure.",
    "the air tastes of copper; healing is halved.",
    "a distant bell tolls when anyone speaks a true name.",
    "the room remembers: returning adds a new hazard.",
    "noises are muffled; ranged attacks are disadvantaged.",
    "a faint aurora outlines invisible things.",
]

def synthesize_mod(rng: random.Random, mod_roll_1_600: int) -> str:
    """
    We don't have the external Appendix Tables, so we map 1-600 onto
    a deterministic "procedural appendix" that feels like a big table.
    """
    # spread the 1-600 space across three dimensions for variety
    a = MOD_ADJECTIVES[(mod_roll_1_600 * 7) % len(MOD_ADJECTIVES)]
    n = MOD_NOUNS[(mod_roll_1_600 * 11) % len(MOD_NOUNS)]
    t = MOD_TWISTS[(mod_roll_1_600 * 13) % len(MOD_TWISTS)]
    # occasional "major mod"
    if mod_roll_1_600 % 50 == 0:
        return f"Major Mod #{mod_roll_1_600}: {a} {n}; {t} Also: *a guardian awakens if you loot anything.*"
    return f"Mod #{mod_roll_1_600}: {a} {n}; {t}"

# ----------------------------
# Unique Room Library (creative replacement for WM14)
# ----------------------------

UNIQUE_ROOMS = [
    "The Hanging Court — chandeliers of bone sway over a trial in progress; the judge is a masked echo of the loudest PC.",
    "The Map That Eats Maps — a mural re-draws itself using any parchment you unroll; it leaves bite marks.",
    "The Choirwell — a dry well that sings in harmonies; drop a coin to learn a secret, drop blood to change the next room.",
    "The Door Museum — hundreds of doors on stands; opening one steals a memory and replaces it with a key.",
    "The Still-Beast Menagerie — glass cages hold sleeping predators; loud noises crack the glass.",
    "The Feast of Dust — banquet tables laid with ash; eating grants visions and a cough that speaks prophecies.",
    "The Clock of Teeth — a giant pendulum clock; each tick swaps two small objects in the party’s packs.",
    "The Inverted Chapel — pews on the ceiling; prayers fall upward, and the altar is a trapdoor.",
    "The Library of Wet Paper — books are readable only while soaked; the water is drawn from your canteens.",
    "The Spiral Orchard — fruit grows from stalactites; each fruit is a spell component… with a price.",
    "The Stone Dentist — a statue offers ‘free’ repairs; it removes curses by removing teeth.",
    "The Mirror Forge — reflections can be hammered into tools; each tool is missing one mundane property.",
    "The Room of Second Footprints — a second set of tracks mirrors the party, one step ahead.",
    "The Coral Stair — a staircase made of living coral; it grows toward the strongest magic source.",
    "The Tax Office of the Dead — ledgers demand payment for every monster killed in the dungeon.",
    "The Lantern Sea — thousands of lanterns float in darkness; blowing one out extinguishes a fear.",
    "The Orchard of Names — apples bear names; eating one changes your name in the world for a day.",
    "The Painted River — water flows like ink; touching it stains equipment with helpful runes… temporarily.",
    "The Bone Carousel — mounts made of ribs; ride one and arrive at a random exit with momentum.",
    "The Vault of Borrowed Voices — bottled voices; releasing one casts a spell but removes a word from your speech until dawn.",
]

def pick_unique_room(rng: random.Random) -> str:
    return choose(rng, UNIQUE_ROOMS)

# ----------------------------
# Data structures
# ----------------------------

@dataclass
class GeneratedRoom:
    index: int
    depth: int
    room_type: str
    geometry: str
    exits: List[str]
    contains: List[str]
    treasure: Optional[str] = None
    treasure_details: Optional[str] = None
    mods: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    loot_multiplier: int = 1

@dataclass
class DungeonResult:
    seed: int
    title: str
    rooms: List[GeneratedRoom]
    summary: Dict[str, Any]
    # Visual map (dungeonmap.Dungeon when available)
    map_dungeon: Optional[Any] = None


# ----------------------------
# Rolling helpers
# ----------------------------

def roll_range_table(rng: random.Random, table: List[Tuple[int,int,str]], sides: int) -> str:
    roll = d(rng, sides)
    for lo, hi, v in table:
        if lo <= roll <= hi:
            return v
    return table[0][2]

def roll_room_geometry(rng: random.Random) -> str:
    base = choose(rng, ROOMS)
    if base.startswith("Special Shape"):
        shape = roll_range_table(rng, SPECIAL_SHAPES, 20)
        size = roll_range_table(rng, SPECIAL_SIZE, 20)
        return f"{shape} — {size}"
    return base

def roll_exits(rng: random.Random) -> List[str]:
    res = roll_range_table(rng, EXITS, 20)
    if res == "Roll Twice":
        a = roll_range_table(rng, EXITS, 20)
        b = roll_range_table(rng, EXITS, 20)
        # avoid infinite recursion; treat "Roll Twice" as "Straight" if appears again
        a = "Straight" if a == "Roll Twice" else a
        b = "Straight" if b == "Roll Twice" else b
        return sorted(set((a + " / " + b).split(" / ")))
    return sorted(set(res.split(" and ")))

def roll_contains(rng: random.Random) -> List[str]:
    res = roll_range_table(rng, ROOM_CONTAINS, 20)
    if res == "Roll Twice":
        a = roll_range_table(rng, ROOM_CONTAINS, 20)
        b = roll_range_table(rng, ROOM_CONTAINS, 20)
        if a == "Roll Twice":
            a = "Remnants of the Past"
        if b == "Roll Twice":
            b = "Tricks and Traps"
        out = [a, b]
        # cumulative if "Roll Twice" again not possible after guard
        return out
    return [res]

def roll_treasure(rng: random.Random) -> Tuple[str, str]:
    kind = roll_range_table(rng, TREASURES, 20)
    container = roll_range_table(rng, TREASURE_CONTAINER, 20)
    trap = roll_range_table(rng, TREASURE_TRAP, 20)
    conceal = roll_range_table(rng, TREASURE_CONCEALMENT, 20)
    # pick item detail
    if kind == "Mundane Items":
        item = choose(rng, MUNDANE_ITEMS)
    elif kind == "Food":
        item = choose(rng, FOOD)
    elif kind == "Magical Items":
        item = choose(rng, MAGIC_ITEMS)
    elif kind == "Fantastic Items":
        item = choose(rng, FANTASTIC_ITEMS)
    else:
        item = choose(rng, MAJOR_TREASURES)
    detail = f"{item} — in {container}. Concealment: {conceal}. Trap: {trap}."
    return kind, detail

# ----------------------------
# Normal room "main passage" micro-sim
# ----------------------------

def roll_main_passage_event(rng: random.Random) -> str:
    return roll_range_table(rng, MAIN_PASSAGE, 20)

def resolve_passage_event(rng: random.Random, event: str) -> List[str]:
    """
    Converts passage events into descriptive notes. This is a "creative implementation":
    we treat the table like a *walk simulator* that accumulates corridor beats until a room is reached.
    """
    notes: List[str] = []
    if event.startswith("Continue Straight"):
        prop = choose(rng, PASSAGE_PROPERTIES)
        notes.append(f"Corridor continues: {prop}")
    elif event == "Door":
        notes.append(f"Door: {DOORS[d(rng, 20)-1]}")
    elif event == "Side Passage(s)":
        n = roll_range_table(rng, SIDE_PASSAGES, 20)
        angle = roll_range_table(rng, PASSAGE_ANGLE, 20)
        notes.append(f"Side passage: {n}; first branches at {angle}.")
    elif event == "Passage Turn":
        angle = roll_range_table(rng, PASSAGE_ANGLE, 20)
        notes.append(f"Passage turn: {angle}.")
    elif event == "Room":
        # handled by caller, but add corridor flavor
        notes.append("A doorframe opens into a chamber.")
    elif event == "Passage End":
        notes.append("Passage ends in a dead wall / collapse / sealed arch.")
    elif event == "Tricks and Traps":
        notes.append(f"Trap in corridor: {choose(rng, TRICKS_TRAPS)}")
    elif event == "Monster Encounters":
        notes.append("Monster presence: tracks, smell, distant snarls (roll your monster table).")
    elif event == "Other Encounters":
        notes.append(f"Encounter beat: {choose(rng, OTHER_ENCOUNTERS)}")
    return notes

# ----------------------------
# Room type effects
# ----------------------------

def mods_for_room_type(rng: random.Random, room_type: str) -> int:
    if room_type == "Normal":
        return 0
    if room_type == "Special":
        return 2
    if room_type == "Rare":
        return d(rng, 8)  # + 1d8 mods
    if room_type == "Unique":
        return 0
    if room_type == "Legendary":
        return d(rng, 8)  # unique + 1d8 mods
    if room_type == "Epic":
        return d(rng, 8)  # blended unique + 1d8
    return 0

def loot_multiplier(room_type: str) -> int:
    if room_type == "Legendary":
        return 2
    if room_type == "Epic":
        return 7
    return 1

# ----------------------------
# Map layout generation
# ----------------------------

def _geometry_to_cells(rng: random.Random, geometry: str) -> Tuple[int, int]:
    """Convert a geometry string (mostly in feet) into grid cell dimensions.

    Assumes 1 cell ≈ 5 feet. Keeps results within a reasonable range.
    For 'Special Size' entries (sq ft), we derive a plausible rectangle.
    """
    g = geometry
    # Common patterns like "Square 20'×20'" or "Rectangle 10'×40'"
    import re
    m = re.search(r"(\d+)\s*'\s*[×x]\s*(\d+)\s*'", g)
    if m:
        a = int(m.group(1))
        b = int(m.group(2))
        return (clamp(max(2, a // 5), 2, 28), clamp(max(2, b // 5), 2, 28))

    # Special size: starts with a number like "1,300 sq ft" or "10,000 sq ft"
    m2 = re.search(r"([0-9,]+)\s*sq\s*ft", g)
    if m2:
        area_ft2 = int(m2.group(1).replace(",", ""))
        # Convert to cell^2 using (5ft)^2 = 25 ft2
        area_cells = max(4, area_ft2 // 25)
        # Choose an aspect ratio 1:1 to 1:3
        aspect = rng.uniform(1.0, 3.0)
        w = int((area_cells / aspect) ** 0.5)
        h = int(w * aspect)
        return (clamp(w, 3, 30), clamp(h, 3, 30))

    # Fallback: mid-sized room
    return (rng.randint(4, 10), rng.randint(4, 10))


def _rects_intersect(ax: int, ay: int, aw: int, ah: int, bx: int, by: int, bw: int, bh: int, pad: int) -> bool:
    ax1, ay1 = ax - pad, ay - pad
    ax2, ay2 = ax + aw + pad, ay + ah + pad
    bx1, by1 = bx - pad, by - pad
    bx2, by2 = bx + bw + pad, by + bh + pad
    return not (ax2 <= bx1 or bx2 <= ax1 or ay2 <= by1 or by2 <= ay1)


def _carve_room(grid: List[List[int]], x: int, y: int, w: int, h: int) -> None:
    for yy in range(y, y + h):
        if yy < 0 or yy >= len(grid):
            continue
        row = grid[yy]
        for xx in range(x, x + w):
            if 0 <= xx < len(row):
                row[xx] = 1


def _carve_corridor(grid: List[List[int]], pts: List[Tuple[int, int]], width: int = 1) -> None:
    half = width // 2

    def carve_cell(cx: int, cy: int) -> None:
        for dy in range(-half, half + 1):
            for dx in range(-half, half + 1):
                x = cx + dx
                y = cy + dy
                if 0 <= y < len(grid) and 0 <= x < len(grid[0]):
                    grid[y][x] = 1

    for i in range(len(pts) - 1):
        x1, y1 = pts[i]
        x2, y2 = pts[i + 1]
        carve_cell(x1, y1)
        if x1 == x2:
            step = 1 if y2 > y1 else -1
            for y in range(y1, y2 + step, step):
                carve_cell(x1, y)
        elif y1 == y2:
            step = 1 if x2 > x1 else -1
            for x in range(x1, x2 + step, step):
                carve_cell(x, y1)
        else:
            # Should not happen; corridors are manhattan
            carve_cell(x2, y2)


def _l_path(rng: random.Random, a: Tuple[int, int], b: Tuple[int, int]) -> List[Tuple[int, int]]:
    """Simple manhattan corridor polyline."""
    (x1, y1), (x2, y2) = a, b
    if rng.random() < 0.5:
        mid = (x2, y1)
    else:
        mid = (x1, y2)
    return [a, mid, b]


def _door_from_corridor_entry(entry: Tuple[int, int], nxt: Tuple[int, int], secret: bool, notes: str) -> MapDoor:
    ex, ey = entry
    nx, ny = nxt
    # If corridor goes horizontally, door sits on vertical wall (V), and vice versa.
    if nx != ex:
        orient = "V"
    else:
        orient = "H"
    return MapDoor(x=ex, y=ey, orientation=orient, secret=secret, notes=notes)


def build_map_layout(cfg: DungeonGenConfig, rng: random.Random, gen_rooms: List[GeneratedRoom]) -> Tuple[MapDungeon, Dict[int, int]]:
    """Place rooms on a grid and connect them with corridors.

    This is intentionally 'OSR map-ish': rooms are packed via a wandering
    placement heuristic, with occasional extra loops.
    """
    W, H = int(cfg.map_width), int(cfg.map_height)
    grid: List[List[int]] = [[0 for _ in range(W)] for _ in range(H)]

    placed: List[MapRoom] = []
    id_map: Dict[int, int] = {}

    # Start near center
    curx, cury = W // 2, H // 2

    for idx, gr in enumerate(gen_rooms, start=1):
        rw, rh = _geometry_to_cells(rng, gr.geometry)

        # Allow deeper rooms to trend slightly larger (subtle)
        if gr.depth >= 21 and rng.random() < 0.35:
            rw = clamp(rw + rng.randint(0, 3), 3, 32)
            rh = clamp(rh + rng.randint(0, 3), 3, 32)

        # Try placing near previous room in a random direction
        placed_room: Optional[MapRoom] = None
        for attempt in range(60):
            if placed:
                base = placed[-1]
                bx, by = base.center
            else:
                bx, by = curx, cury

            dir = rng.choice([(1,0), (-1,0), (0,1), (0,-1)])
            dist = rng.randint(6, 14)
            px = bx + dir[0] * dist - rw // 2
            py = by + dir[1] * dist - rh // 2

            # Clamp in bounds
            px = clamp(px, 1, W - rw - 2)
            py = clamp(py, 1, H - rh - 2)

            ok = True
            for r in placed:
                if _rects_intersect(px, py, rw, rh, r.x, r.y, r.w, r.h, cfg.room_padding):
                    ok = False
                    break
            if ok:
                placed_room = MapRoom(
                    id=idx,
                    x=px,
                    y=py,
                    w=rw,
                    h=rh,
                    tag="randungeon",
                    name=f"Room {gr.index}: {gr.room_type}",
                    description=gr.geometry,
                    gm_notes="\n".join(gr.notes[:6])
                )
                break

            # Occasionally jitter center so the layout doesn't get stuck
            if attempt % 15 == 14:
                curx = clamp(curx + rng.randint(-8, 8), 2, W - 3)
                cury = clamp(cury + rng.randint(-8, 8), 2, H - 3)

        if placed_room is None:
            # Fallback: random spot
            for attempt in range(200):
                px = rng.randint(1, max(1, W - rw - 2))
                py = rng.randint(1, max(1, H - rh - 2))
                ok = True
                for r in placed:
                    if _rects_intersect(px, py, rw, rh, r.x, r.y, r.w, r.h, cfg.room_padding):
                        ok = False
                        break
                if ok:
                    placed_room = MapRoom(id=idx, x=px, y=py, w=rw, h=rh, tag="randungeon")
                    break

        if placed_room is None:
            # Worst case: squeeze it in (overlap allowed) rather than fail the plugin.
            placed_room = MapRoom(id=idx, x=clamp(curx - rw // 2, 1, W - rw - 2), y=clamp(cury - rh // 2, 1, H - rh - 2), w=rw, h=rh, tag="randungeon")

        placed.append(placed_room)
        id_map[gr.index] = placed_room.id
        _carve_room(grid, placed_room.x, placed_room.y, placed_room.w, placed_room.h)

    # Corridors + doors
    corridors: List[MapCorridor] = []
    doors: List[MapDoor] = []

    def connect(a: MapRoom, b: MapRoom, secret: bool = False, notes: str = "") -> None:
        path = _l_path(rng, a.center, b.center)
        corridors.append(MapCorridor(points=path, secret=secret))
        _carve_corridor(grid, path, width=cfg.corridor_width)

        # Doors at entry points (closest points to room centers)
        if len(path) >= 2:
            # Door at the room A side
            doors.append(_door_from_corridor_entry(path[0], path[1], secret=secret, notes=notes))
            # Door at the room B side
            doors.append(_door_from_corridor_entry(path[-1], path[-2], secret=secret, notes=notes))

    for i in range(1, len(placed)):
        connect(placed[i - 1], placed[i], secret=False)

    # Extra loops: connect a few random pairs
    if len(placed) >= 4 and cfg.extra_loops > 0:
        attempts = max(1, int(len(placed) * cfg.extra_loops))
        for _ in range(attempts):
            a = rng.choice(placed)
            b = rng.choice(placed)
            if a.id == b.id:
                continue
            # Skip adjacent (already connected) most of the time
            if abs(a.id - b.id) <= 1 and rng.random() < 0.8:
                continue
            secret = (rng.randint(1, 20) == 20)
            connect(a, b, secret=secret, notes="loop")

    return MapDungeon(width=W, height=H, rooms=placed, corridors=corridors, doors=doors, grid=grid), id_map

# ----------------------------
# Main generator
# ----------------------------

@dataclass
class DungeonGenConfig:
    title: str = "The Infinite Corridor"
    rooms: int = 12
    start_depth: int = 0
    seed: int = 1337
    # "creative knobs"
    corridor_beats_min: int = 1
    corridor_beats_max: int = 4
    allow_special_passages: bool = True
    annotate_with_exploration_tables: bool = True

    # Map layout settings (grid units, not feet)
    map_width: int = 80
    map_height: int = 60
    room_padding: int = 1
    corridor_width: int = 1
    extra_loops: float = 0.15  # 0..1 chance to add extra connections

def generate_dungeon(cfg: DungeonGenConfig, rng: random.Random) -> DungeonResult:
    rooms: List[GeneratedRoom] = []

    for i in range(cfg.rooms):
        depth = cfg.start_depth + i
        rt = roll_room_type(rng, depth)

        geom = roll_room_geometry(rng)
        exits = roll_exits(rng)
        contains = roll_contains(rng)

        r = GeneratedRoom(
            index=i+1,
            depth=depth,
            room_type=rt,
            geometry=geom,
            exits=exits,
            contains=contains,
            loot_multiplier=loot_multiplier(rt),
        )

        # Corridor micro-sim: accumulate a few beats per room for "map key" feel
        beats = rng.randint(cfg.corridor_beats_min, cfg.corridor_beats_max)
        for _ in range(beats):
            ev = roll_main_passage_event(rng)
            r.notes.extend(resolve_passage_event(rng, ev))
            if ev == "Room":
                break

        # Occasional special passage beat
        if cfg.allow_special_passages and d(rng, 20) == 20:
            r.notes.append(f"Special passage feature: {SPECIAL_PASSAGES[d(rng,20)-1]}")

        # Unique / Legendary / Epic room description
        if rt == "Unique":
            r.notes.append(f"Unique feature: {pick_unique_room(rng)}")
        elif rt == "Legendary":
            r.notes.append(f"Unique feature: {pick_unique_room(rng)}")
            r.notes.append("Legendary pressure: the dungeon notices you; wandering checks are more frequent.")
        elif rt == "Epic":
            a = pick_unique_room(rng)
            b = pick_unique_room(rng)
            if a == b:
                b = pick_unique_room(rng)
            r.notes.append(f"Epic blend: {a}")
            r.notes.append(f"…and also: {b}")
            r.notes.append("Epic rule: the room rewrites one exit when you leave.")

        # Contents resolution
        if "Treasures" in r.contains:
            kind, detail = roll_treasure(rng)
            r.treasure = kind
            r.treasure_details = detail

        if "Tricks and Traps" in r.contains:
            r.notes.append(f"Room trap: {choose(rng, TRICKS_TRAPS)}")

        if "Other Encounters" in r.contains:
            r.notes.append(f"Room encounter: {choose(rng, OTHER_ENCOUNTERS)}")

        if "Monsters" in r.contains:
            r.notes.append("Room monsters: roll or pick based on dungeon theme (suggestion: scale with depth).")

        # Mods
        mod_count = mods_for_room_type(rng, rt)
        for _ in range(mod_count):
            mr = rng.randint(1, 600)
            r.mods.append(synthesize_mod(rng, mr))

        rooms.append(r)

    summary = {
        "rooms": len(rooms),
        "by_type": _count_by([r.room_type for r in rooms]),
    }

    result = DungeonResult(seed=cfg.seed, title=cfg.title, rooms=rooms, summary=summary)
    # Build a visual dungeon map using a lightweight corridor-walk placer.
    try:
        result.map_dungeon = build_visual_map(result, rng)
    except Exception:
        # Never brick generation if map building fails
        result.map_dungeon = None
    return result

def _count_by(items: List[str]) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for it in items:
        out[it] = out.get(it, 0) + 1
    return out

# ----------------------------
# Exploration tables (Hexmaster-like pattern)
# ----------------------------

@dataclass
class TableResult:
    name: str
    roll: int
    text: str


def roll_exploration_table(rng: random.Random, table_name: str) -> TableResult:
    """
    Themed for this module: 'Infinite Dungeon / shifting corridors / odd bureaucracy of the underworld'.
    Pattern match to Hexmaster-style tables:
      - quick d20 sensory/action tables
      - heavyweight d100 tables where 61–100 = roll twice (stacking details)
    """
    d20_tables: Dict[str, List[str]] = {
        "Wandering Omen (d20)": WANDERING_OMEN,
        "Dungeon Sound (d20)": DUNGEON_SOUNDS,
        "Dungeon Smell (d20)": DUNGEON_SMELLS,
        "Door Quirk (d20)": DOOR_QUIRKS,
        "Trap Tell (d20)": TRAP_TELLS,
        "Weird Treasure Tag (d20)": TREASURE_TAGS,
        "Faction Sign (d20)": FACTION_SIGNS,
        "Wandering Monster Mood (d20)": MONSTER_MOODS,
    }

    d100_roll_twice_tables: Dict[str, List[str]] = {
        "Room Dressing (d100; 61–100 roll twice)": ROOM_DRESSING_100,
        "Exploration Complication (d100; 61–100 roll twice)": COMPLICATIONS_100,
        "Dungeon Boon (d100; 61–100 roll twice)": BOONS_100,
    }

    if table_name in d20_tables:
        entries = d20_tables[table_name]
        roll = d(rng, 20)
        return TableResult(name=table_name, roll=roll, text=entries[roll-1])

    if table_name in d100_roll_twice_tables:
        entries = d100_roll_twice_tables[table_name]
        roll = d(rng, 100)
        if roll <= 60:
            return TableResult(name=table_name, roll=roll, text=entries[roll-1])
        # 61-100: roll twice, cumulative (and if you roll 61+ again, keep stacking up to 3 total)
        parts: List[str] = []
        rolls: List[int] = []
        remaining = 2
        safety = 0
        while remaining > 0 and safety < 10:
            safety += 1
            rr = d(rng, 100)
            rolls.append(rr)
            if rr <= 60:
                parts.append(entries[rr-1])
            else:
                # roll twice again (stack)
                remaining += 1
            remaining -= 1
            if len(parts) >= 3:
                break
        shown = f"{roll} ⇒ rolled: {', '.join(str(x) for x in rolls)}"
        return TableResult(name=table_name, roll=roll, text=f"{shown}\n- " + "\n- ".join(parts))

    raise KeyError(f"Unknown table: {table_name}")

# --- d20 tables ---

WANDERING_OMEN = [
    "A corridor ‘breathes’—dust puffs outward; something large moved beyond the walls.",
    "Your torch flame leans toward the nearest secret door for a heartbeat.",
    "A single wet footprint appears ahead, then dries instantly.",
    "Distant applause. It stops when you speak above a whisper.",
    "A coin rolls past, against the slope. It’s warm.",
    "The air tastes like ink; written words blur until you leave this area.",
    "A bell tolls once; everyone remembers a different childhood moment.",
    "A draft carries the smell of cooking… but no smoke.",
    "A keyring jingles inside someone’s pack—no one put it there.",
    "A tiny paper receipt flutters down: ‘PAID IN FULL’ (signed in blood).",
    "A shadow darts across the ceiling, too fast to see.",
    "A trickle of water runs uphill and vanishes into a crack.",
    "A door you passed earlier is now bricked over (fresh mortar).",
    "A faint chorus repeats the party’s last sentence in harmony.",
    "A spiderweb spells a word: ‘TURN BACK’ (in your handwriting).",
    "A gust extinguishes nonmagical light; phosphorescent lichen glows instead.",
    "A distant argument echoes—one voice is clearly yours.",
    "A map in someone’s pack updates: a new room is sketched in red.",
    "A gentle rain falls… from the ceiling only over metal objects.",
    "A slow, polite knocking from inside the wall: knock… knock…",
]

DUNGEON_SOUNDS = [
    "Chains dragged slowly, then dropped.",
    "A faraway lullaby sung out of tune.",
    "Wet clicking, like crab legs on stone.",
    "Ink dripping into a metal bowl.",
    "A page turning itself every ten seconds.",
    "Breathing through a mask’s filter.",
    "Small stones falling in a deep shaft.",
    "Muffled cheering from behind a door.",
    "A flute note that never resolves.",
    "A distant quarry whistle—industrial and wrong.",
    "Glass chimes struck by no wind.",
    "A heartbeat that is not yours.",
    "A quill scratching, writing quickly.",
    "A low chant counting numbers.",
    "A hiss followed by the smell of ozone.",
    "Bootsteps keeping pace beside you, unseen.",
    "A thunderclap from far underground.",
    "A laugh, then a polite cough.",
    "A door latch testing itself.",
    "Silence so heavy it hurts your ears.",
]

DUNGEON_SMELLS = [
    "Cold stone after rain.",
    "Hot iron and old blood.",
    "Mildew and crushed mushrooms.",
    "Sweet incense masking rot.",
    "Ozone and burned hair.",
    "Candle wax and cinnamon.",
    "Wet dog and brine.",
    "Ink and citrus peel.",
    "Sulfur and charcoal.",
    "Honey over carrion.",
    "Dry parchment and dust.",
    "Sour wine spilled long ago.",
    "Rosewater over sewage.",
    "Metal polish and bile.",
    "Pine resin and smoke.",
    "Rotten apples and spice.",
    "Chalk and antiseptic.",
    "Lavender and mold.",
    "Fresh bread… impossibly fresh.",
    "Nothing at all: the air is ‘blank’.",
]

DOOR_QUIRKS = [
    "The door opens only if someone tells it a secret.",
    "The door is warm like skin; it ‘swallows’ light at the edge.",
    "The handle is a key already inserted—turning it costs a memory.",
    "The door is painted on; it becomes real if you knock politely.",
    "The hinges squeal in perfect mimicry of your voice.",
    "The door insists on being introduced to each party member.",
    "The door opens inward… into a tiny room that’s bigger inside.",
    "The door is locked, but apologizes constantly.",
    "The door is barred with a bone; breaking it releases a curse-wisp.",
    "The door is two doors, overlapping; choose which reality to enter.",
    "The keyhole stares like an eye and tracks movement.",
    "The door bleeds sap when struck.",
    "The door is missing; the frame opens like curtains.",
    "The door is upside-down; opening it changes gravity in the next room.",
    "A plaque reads: EMPLOYEES ONLY (it’s true).",
    "The door opens, then shuts behind you without a sound.",
    "The door opens to a hallway that isn’t on your map.",
    "The door refuses to open if you are armed (it can be bribed).",
    "The door opens only at the count of three (it likes rhythm).",
    "The door is already open—yet something holds it like a hand.",
]

TRAP_TELLS = [
    "Dust is swept clean in a perfect rectangle (pressure plate).",
    "A tiny pinhole in the wall aimed at ankle height.",
    "The stones are too evenly spaced here.",
    "Fresh scratches on the floor near a corner.",
    "A faint chemical smell (oil, acid, or gas).",
    "A loose tile that clicks when tapped.",
    "A hair-thin wire catching torchlight.",
    "New mortar in one ceiling seam.",
    "A dead rat lies here—oddly intact.",
    "A puddle that is not water (it doesn’t ripple).",
    "The air is warmer in a straight line (flame jet).",
    "A breeze from behind the wall (moving mechanism).",
    "A glyph half-erased as if scratched off.",
    "Tiny holes in the ceiling (needles / darts).",
    "Footprints stop abruptly, then resume two steps later.",
    "An old warning scratched into stone: DON’T STEP.",
    "Obvious bait: shiny object dead-center.",
    "A rope/chain disappears into a floor crack.",
    "Unnatural quiet (sound dampening field).",
    "A faint shimmer across the floor like heat haze (illusion).",
]

TREASURE_TAGS = [
    "Stamped with a receipt number.",
    "Bound in red thread that tightens when lied to.",
    "Smells faintly of cinnamon and ozone.",
    "Wrapped in a map scrap that changes when unfolded.",
    "Warm to the touch, even in water.",
    "Covered in tiny bite marks (something tasted it).",
    "Etched with the party’s names… slightly misspelled.",
    "Held in wax marked with a courthouse seal.",
    "Rattles as if something inside is alive.",
    "Coated in glittering dust that sticks to skin.",
    "Mirrors your reflection a half-second late.",
    "Tastes like metal if licked (don’t).",
    "Has a tag: RETURN TO SENDER (the sender is the dungeon).",
    "Bleeds ink when cut.",
    "Sings softly if held close to the ear.",
    "Casts a shadow even in total darkness.",
    "Leaves wet footprints behind whoever carries it.",
    "Feels heavier every hour.",
    "Cold where your hand touches it; warm elsewhere.",
    "Perfectly clean in a filthy place (suspicious).",
]

MONSTER_MOODS = [
    "Hunting: follows the weakest-looking PC first.",
    "Territorial: warns once, then attacks.",
    "Starving: will bargain for food or corpses.",
    "Curious: steals a small item and retreats.",
    "Cowardly: fights only if cornered; uses traps.",
    "Fanatical: chants, calls reinforcements.",
    "Injured: leaves a blood trail; desperate.",
    "Clever: sets an ambush behind a door.",
    "Sleepy: may be bypassed with quiet tactics.",
    "Proud: challenges a champion to single combat.",
    "Parasitic: tries to attach, mark, or infect.",
    "Mimicry: imitates a voice the party trusts.",
    "Jealous: targets magic users or obvious wealth.",
    "Playful: nonlethal harassment, but escalates.",
    "Silent: no calls, no taunts—just pressure.",
    "Bureaucratic: demands ‘papers’ or ‘tolls’ to pass.",
    "Religious: mistakes the party for omens.",
    "Pack-minded: always tries to flank and isolate.",
    "Vengeful: recognizes the party from earlier rooms (even if impossible).",
    "Lost: confused creature seeking the ‘correct’ corridor.",
]

# --- d100 tables (61–100 = roll twice) ---
ROOM_DRESSING_100 = [
    # 1-60 only (61-100 triggers roll twice)
    "A chalk circle with bootprints crossing it.",
    "A heap of broken lantern glass (still faintly warm).",
    "A narrow shelf of dusty ledgers tied with red string.",
    "A collapsed cot and a tin cup nailed to the wall.",
    "A mosaic floor tile missing, revealing a crawlspace draft.",
    "A smear of luminous fungus in the shape of a door.",
    "A stack of bones arranged like polite seating.",
    "A cracked mirror angled to reflect the ceiling only.",
    "A corded bell pull labeled ‘EMERGENCY’.",
    "A pile of damp receipts in multiple languages.",
    "A small shrine of teeth and copper coins.",
    "A puddle that reflects a different room.",
    "A hanging cage with a lock but no hinges.",
    "A stone plinth with thumbprints worn into it.",
    "A painting that re-arranges the party when no one looks.",
    "A heap of iron keys fused together.",
    "A faintly glowing seam of mortar across one wall.",
    "A statue missing its face; the face sits on the floor nearby.",
    "A lectern with a blank page that absorbs ink.",
    "A wind chime made of arrowheads.",
    "A pile of rations with a date: ‘TOMORROW’.",
    "A set of footprints that end at the ceiling.",
    "A rug that is too clean; it hides something.",
    "A copper pipe sweating black water.",
    "A doorway bricked over with fresh mortar.",
    "A slit in the wall that whispers names.",
    "A bucket of sand with a perfect handprint in it.",
    "A stone bench carved with tally marks.",
    "A circle of salt with a single coin at the center.",
    "A chain hanging from above, cut cleanly at waist height.",
    "A crate of books that are all the same book.",
    "A pile of broken arrows with ink-stained fletching.",
    "A brass plaque listing room numbers (some scratched out).",
    "A child’s toy that walks three steps, then stops.",
    "A heap of melted candlewax shaped like a face.",
    "A skull with a tiny padlock on its jaw.",
    "A mural map that is wrong… but helpful later.",
    "A string of paper lanterns with no oil inside.",
    "A hidden alcove stuffed with damp cloth masks.",
    "A narrow drain that pulls at loose coins.",
    "A stack of perfectly folded cloaks (sizes don’t match).",
    "A slab of stone that is gently warm like skin.",
    "A chalk arrow that points to itself.",
    "A cask labeled ‘SILENCE’ (sloshing inside).",
    "A metal grate that hums when approached.",
    "A heap of rusted weapons arranged by size.",
    "A bowl of water with a floating compass needle that spins.",
    "A rope bridge rolled up like a carpet.",
    "A hanging sign: ‘CLOSED FOR INVENTORY’.",
    "A bundle of dried herbs that smell like ozone.",
    "A locked filing cabinet with teeth marks on it.",
    "A pile of coins glued to the floor in a spiral.",
    "A book stand holding a book that screams when opened (quietly).",
    "A fresh bootprint in wet clay—too large to be human.",
    "A melted lock, as if by acid.",
    "A chalkboard listing ‘TODAY’S RULES’ (blank).",
    "A small brass hourglass with sand running upward.",
    "A stone basin full of ink instead of water.",
    "A wind that only touches hair and cloth.",
    "A thin layer of frost on one wall only, shaped like a doorway.",
]
COMPLICATIONS_100 = [
    "A door you used earlier is now an exit to somewhere else.",
    "The next light source you ignite burns half as long.",
    "A loud noise here triggers an immediate wandering check.",
    "The floor is slick; the first sprint causes a fall unless careful.",
    "A stray magic aura scrambles minor illusions.",
    "A room number appears on the wall—your current room is unnumbered.",
    "Something steals one ration; you find it later in a different pack.",
    "A thin fog makes tracking difficult; footprints blur.",
    "The dungeon ‘politely’ closes one random exit behind you.",
    "Your shadows misbehave; stealth is harder but ambush is easier.",
    "A paper form appears: ‘DECLARATION OF INTENT’—lying has consequences.",
    "The next treasure found is trapped (even if it shouldn’t be).",
    "A distant gong sounds; all doors lock for 1 minute.",
    "The air grows heavy; carrying capacity effectively reduced.",
    "All spoken numbers are wrong until you leave this area.",
    "A friendly creature offers help, but demands a name as payment.",
    "The next trap is obvious, but its trigger is not.",
    "The next monster encountered is already injured (something else fought it).",
    "A corridor loops; without a mark, you return to the same junction.",
    "A harmless rain falls; it corrodes cheap metal.",
    "Your map updates with a new room that wasn’t there.",
    "The dungeon starts counting your steps aloud (only you hear it).",
    "A random item is duplicated—but the copy is cursed.",
    "Doors become slightly smaller; large creatures struggle.",
    "The next short rest draws attention unless hidden.",
    "A polite voice asks for ‘toll’: 1 coin per person or 10 minutes lost.",
    "The next secret door you find is already open… from the other side.",
    "A harmless spectral clerk follows, writing notes.",
    "The dungeon changes the smell of blood; predators gain advantage.",
    "A corridor hum interferes with concentration checks.",
    "A painted arrow appears, pointing the least safe route.",
    "A mechanical click begins; something will happen in 3 turns.",
    "A door insists on a password; wrong answers trigger harmless but loud alarms.",
    "A patch of floor is reversed; you walk on the ceiling for 10'.",
    "You find your own footprints heading back toward you.",
    "A mild curse makes everyone speak in questions for an hour.",
    "A fountain offers clean water, but also a minor geas.",
    "A grate exhales spores; torches sputter and dim.",
    "A bell rings whenever someone tells the truth.",
    "A friendly goblin offers a shortcut… for a favor later.",
    "A corridor becomes a one-way slope; climbing back is hard.",
    "A hinge squeak alerts nearby patrols.",
    "Your lantern shows hidden writing, but drains oil faster.",
    "A door frame resets your marching order randomly.",
    "The next room’s exits are mislabeled; left/right swap.",
    "A magical draft steals one spoken spell component.",
    "A quiet weeping sound makes morale checks harder.",
    "A long hallway becomes 1' narrow halfway through.",
    "A floor tile teleports a dropped item to the last room.",
    "The dungeon becomes ‘fair’: the next trap also hinders monsters.",
    "A hidden clerk’s stamp marks your hands; some doors now recognize you.",
    "A shadow tries to trade places with a PC for 1 turn.",
    "The next treasure is ‘accounted for’—removing it triggers pursuit.",
    "You hear your names spoken from far away.",
    "A corridor grows; distance doubles until you turn back.",
    "The dungeon shifts; reroll one previously mapped connection.",
    "A door opens to reveal… the same door from the other side.",
    "A safe-looking rest spot is a mimic ecosystem (non-lethal, annoying).",
    "A harmless illusion makes distances feel wrong; speeds are halved for 1 turn.",
    "A corridor’s slope reverses unexpectedly; dropped items roll away.",
]
BOONS_100 = [
    "A chalk sigil grants advantage on the next navigation check.",
    "A harmless spirit answers one yes/no question truthfully.",
    "A hidden cache contains 1d4 torches or oil flasks.",
    "A door recognizes your ‘authority’ and opens without fuss.",
    "A map fragment reveals one secret door location nearby.",
    "A soothing hum grants a free short-rest benefit in half time.",
    "A blessing of silence: +2 to stealth for one room.",
    "A lucky coin: reroll one d20 roll in this dungeon (then it vanishes).",
    "A spring of clean water removes one level of exhaustion.",
    "A friendly goblin guide shows a safe route (for 1 room).",
    "A candle that burns underwater for 1 hour.",
    "A receipt marked ‘REFUND’: negate one trap effect once.",
    "A compass that points to the nearest treasure for 10 minutes.",
    "A mild ward: the next wandering encounter is delayed.",
    "A door that stays open behind you (no auto-close) for 1 room.",
    "A rune that makes your footsteps sound like a different creature.",
    "A key that opens any mundane lock once (then melts).",
    "A mural grants a tactical hint about the next monster type.",
    "A pocket of fresh air: gas/smoke effects are resisted for 1 room.",
    "A silver bell: ring it to force parley with intelligent foes once.",
    "A mirror shard: glimpse one hidden hazard in the next room.",
    "A small stash of bandages: +1d6 HP on next rest for one PC.",
    "A lantern mote: briefly reveals invisible/illusory for 1 minute.",
    "A friendly clerk’s stamp: one faction will treat you as ‘expected guests’.",
    "A corridor shortcut appears for 1 turn only—take it or lose it.",
    "A blessing of grip: ignore slippery terrain for 1 room.",
    "A door that ‘likes you’: advantage on forcing/lockpicking next door.",
    "A map redraws, removing one false passage.",
    "A charm of steady hands: advantage vs needle/dart traps once.",
    "A ration that tastes like home: morale improves; fear saves advantage once.",
    "A small mechanical bird scouts the next junction then returns.",
    "A tiny fungus patch emits light for 2 hours when harvested.",
    "A mild luck aura: first attack roll next combat has advantage.",
    "A salt line breaks a curse-wisp’s hold (remove one minor curse).",
    "A gift-wrapped item: add one weird treasure tag without curse.",
    "A door label appears: ‘SAFE ROOM’ (it is, for 10 minutes).",
    "A whisper teaches a useful password for a later door.",
    "A hidden alcove contains a note: ‘DON’T PULL THAT’ (it’s correct).",
    "A time skip: the dungeon’s clocks advance, but your torches do not.",
    "A blessing of names: you cannot be magically compelled to speak a true name for 1 day.",
    "A candle flame turns blue: detect poison in food/drink for 1 room.",
    "A friendly echo repeats enemy movements—advantage on initiative once.",
    "A clean bootprint path: avoid one hazard zone automatically.",
    "A small token: trade it at a goblin market for fair value.",
    "A chorus hum steadies spellcasting—advantage on concentration once.",
    "A gentle draft points to the nearest exit for 1 room.",
    "A warm stone: ignore cold effects for 1 room.",
    "A polite warning appears in chalk about the next trap type.",
    "A spare lockpick appears in your pouch (once).",
    "A hint of lavender: advantage on saves vs fear for 10 minutes.",
    "A whispered lullaby grants one PC the benefits of a short rest (once).",
    "A small brass tag: ‘AUTHORIZED’—one locked door opens for free.",
    "A mirror shows the correct left/right in the next junction.",
    "A tiny receipt: ‘ONE FREE PASS’—ignore one toll/guardian demand.",
    "A fountain’s splash cleans acid/slime off gear instantly.",
    "A warm lantern wick: your next flame can’t be extinguished for 10 minutes.",
    "A calm silence: detect lies within 10' for 1 minute (subtle).",
    "A tiny sigil: once, ignore difficult terrain for a turn.",
    "A folded map scrap grants +1 to a single search check.",
    "A soft glow outlines the safest exit at the next junction.",
]

FACTION_SIGNS = [
    "A chalk spiral with a number inside (they mark territory by ‘turns’).",
    "Tiny copper nails hammered in a pattern (a code).",
    "A strip of cloth tied to a pipe, colored like a warning flag.",
    "A prayer card tucked into a crack (recent).",
    "A goblin trade token wedged under a stone.",
    "A wax seal pressed into mud: a crown over an eye.",
    "A neat stack of bones, arranged like a message.",
    "A fresh ration wrapper with a written schedule.",
    "A smear of luminous fungus in arrow shapes.",
    "A ‘Do Not Enter’ sign, politely lettered, nailed from the inside.",
    "A row of candles burned to the same height (ritual timing).",
    "A bell cord dangling from the ceiling (alarm system).",
    "A set of footprints that stop at the wall (secret route).",
    "A small shrine of coins and teeth (offerings).",
    "A map scratched into lead, hidden behind a loose brick.",
    "A circle of salt with a bootprint deliberately crossing it.",
    "A bundle of arrows, all fletched with black paper.",
    "A bloodless corpse posed pointing at an exit.",
    "A note: ‘WE’RE WATCHING’ (signed with a smiling face).",
    "A painted line across the floor: ‘TAX ZONE’ (pay to pass).",
]

# ----------------------------
# Visual map builder (rectangular approximation)
# ----------------------------

def _parse_base_room_dims(geometry: str, rng: random.Random) -> Tuple[int, int, str]:
    """Return (w_cells, h_cells, shape_label) using 5' per cell.

    The dungeonmap renderer supports rectangular rooms only. When the table
    produces a non-rectangular *special* shape, we store the shape as a label
    but still carve an approximate rectangle with roughly the same area.
    """
    g = (geometry or "").strip()

    import re
    import math

    m = re.search(r"(Square|Rectangle)\s+(\d+)'x(\d+)'", g)
    if m:
        shape = m.group(1)
        w_ft = int(m.group(2))
        h_ft = int(m.group(3))
        w = max(3, w_ft // 5)
        h = max(3, h_ft // 5)
        return w, h, shape

    # Special shapes emitted as: "<Shape> — <Size>" where size starts with a sq-ft value.
    if "—" in g:
        shape, size = [p.strip() for p in g.split("—", 1)]
        m2 = re.search(r"([0-9,]+)\s*sq\s*ft", size)
        if m2:
            area_ft2 = int(m2.group(1).replace(",", ""))
            area_cells = max(9, int(area_ft2 / 25))
            ar = rng.choice([1.0, 1.2, 1.4, 1.6, 2.0])
            w = int(max(3, math.sqrt(area_cells * ar)))
            h = int(max(3, math.ceil(area_cells / max(1, w))))
            return min(w, 40), min(h, 40), shape

    return 6, 6, "Room"


def _door_semantics_from_roll(roll: int) -> Tuple[str, str, bool, bool]:
    """(door_type, state, secret, locked) derived from your Doors table roll 1-20."""
    secret = roll in (6, 7, 8, 9, 10)
    locked = roll in (16, 20)

    if roll in (11, 12, 13):
        return "double", "closed", secret, locked
    if roll in (14, 15):
        return "trapdoor", "closed", secret, locked
    if roll == 17:
        return "portcullis", "closed", secret, locked
    if roll == 18:
        return "wooden", "broken", secret, locked
    if roll == 19:
        return "magical", "open", secret, locked
    if roll == 20:
        return "stone", "sealed", secret, locked
    return "wooden", "closed", secret, locked


def build_visual_map(result: DungeonResult, rng: random.Random, width: int = 140, height: int = 100):
    """Create a connected dungeon map for the generated rooms.

    - Rooms are rectangles on a grid.
    - Corridors are Manhattan L-shapes.
    - Doors are placed at corridor-room junctions using the Doors table semantics.

    Returns a dungeonmap.generator.Dungeon instance.
    """
    from campaign_forge.plugins.dungeonmap.generator import Dungeon, Room, Corridor, Door

    n = max(1, len(result.rooms))
    w = int(max(90, min(width, 70 + n * 6)))
    h = int(max(70, min(height, 55 + n * 4)))

    grid = [[0 for _ in range(w)] for _ in range(h)]
    rooms: List[Room] = []
    corridors: List[Corridor] = []
    doors: List[Door] = []

    def clamp(v: int, lo: int, hi: int) -> int:
        return max(lo, min(v, hi))

    def carve_room(rr: Room) -> None:
        for yy in range(rr.y, rr.y + rr.h):
            for xx in range(rr.x, rr.x + rr.w):
                if 0 <= yy < h and 0 <= xx < w:
                    grid[yy][xx] = 1

    def carve_corridor_poly(points: List[Tuple[int, int]]) -> None:
        for i in range(len(points) - 1):
            x1, y1 = points[i]
            x2, y2 = points[i + 1]
            x, y = x1, y1
            if 0 <= y < h and 0 <= x < w:
                grid[y][x] = 1
            while x != x2 or y != y2:
                if x < x2:
                    x += 1
                elif x > x2:
                    x -= 1
                elif y < y2:
                    y += 1
                elif y > y2:
                    y -= 1
                if 0 <= y < h and 0 <= x < w:
                    grid[y][x] = 1

    def intersects_any(x: int, y: int, rw: int, rh: int, pad: int = 2) -> bool:
        for rr in rooms:
            if not (x + rw + pad <= rr.x or rr.x + rr.w + pad <= x or y + rh + pad <= rr.y or rr.y + rr.h + pad <= y):
                return True
        return False

    def closest_edge_cell(room: Room, px: int, py: int) -> Tuple[int, int, str]:
        vx = px - room.center[0]
        vy = py - room.center[1]
        if abs(vx) > abs(vy):
            if vx < 0:
                return room.x, clamp(py, room.y, room.y + room.h - 1), "V"
            return room.x + room.w - 1, clamp(py, room.y, room.y + room.h - 1), "V"
        if vy < 0:
            return clamp(px, room.x, room.x + room.w - 1), room.y, "H"
        return clamp(px, room.x, room.x + room.w - 1), room.y + room.h - 1, "H"

    def connect_rooms(prev: Room, nxt: Room) -> None:
        sx, sy = prev.center
        tx, ty = nxt.center

        elbow = (tx, sy) if rng.random() < 0.6 else (sx, ty)
        pts = [(sx, sy), elbow, (tx, ty)]

        corridors.append(Corridor(points=pts, secret=False))
        carve_corridor_poly(pts)

        # Door into nxt
        dx, dy, ori = closest_edge_cell(nxt, elbow[0], elbow[1])
        roll = rng.randint(1, 20)
        dtype, state, secret, locked = _door_semantics_from_roll(roll)
        doors.append(Door(x=dx, y=dy, orientation=ori, secret=secret, door_type=dtype, state=state, locked=locked))

        # Sometimes a matching door at prev
        if rng.random() < 0.5:
            px, py, pori = closest_edge_cell(prev, elbow[0], elbow[1])
            roll2 = rng.randint(1, 20)
            dtype2, state2, secret2, locked2 = _door_semantics_from_roll(roll2)
            doors.append(Door(x=px, y=py, orientation=pori, secret=secret2, door_type=dtype2, state=state2, locked=locked2))

    # Start room
    first = result.rooms[0]
    rw, rh, _shape = _parse_base_room_dims(first.geometry, rng)
    x0 = (w // 2) - (rw // 2)
    y0 = (h // 2) - (rh // 2)

    r0 = Room(id=1, x=x0, y=y0, w=rw, h=rh, tag=first.room_type.lower())
    r0.name = f"Room 1 — {first.room_type}"
    r0.description = f"{first.geometry}\nContains: {', '.join(first.contains)}"
    carve_room(r0)
    rooms.append(r0)

    # Direction state
    dir_idx = 0

    def dir_vec(di: int) -> Tuple[int, int]:
        return [(1, 0), (0, 1), (-1, 0), (0, -1)][di % 4]

    # Turn bias inspired by Passage Angle: mostly 90-degree turns, occasional U-turn
    turn_choices = [0, 0, 0, 1, 1, -1, -1, 2, -2]

    for i, meta in enumerate(result.rooms[1:], start=2):
        prev = rooms[-1]
        rw2, rh2, _shape2 = _parse_base_room_dims(meta.geometry, rng)

        placed: Optional[Room] = None

        for _attempt in range(80):
            dir_idx = (dir_idx + rng.choice(turn_choices)) % 4
            dx, dy = dir_vec(dir_idx)
            base_len = rng.randint(8, 16) + (meta.depth // 12)

            cx = prev.center[0] + dx * base_len
            cy = prev.center[1] + dy * base_len

            rx = clamp(cx - rw2 // 2, 2, w - rw2 - 3)
            ry = clamp(cy - rh2 // 2, 2, h - rh2 - 3)

            if intersects_any(rx, ry, rw2, rh2, pad=2):
                continue

            nr = Room(id=i, x=rx, y=ry, w=rw2, h=rh2, tag=meta.room_type.lower())
            nr.name = f"Room {i} — {meta.room_type}"
            nr.description = f"{meta.geometry}\nContains: {', '.join(meta.contains)}"

            carve_room(nr)
            connect_rooms(prev, nr)
            placed = nr
            break

        if placed is None:
            # Fallback: place near the previous room with a short hop
            rx = clamp(prev.x + rng.randint(-10, 10), 2, w - rw2 - 3)
            ry = clamp(prev.y + rng.randint(-10, 10), 2, h - rh2 - 3)
            if not intersects_any(rx, ry, rw2, rh2, pad=1):
                nr = Room(id=i, x=rx, y=ry, w=rw2, h=rh2, tag=meta.room_type.lower())
                nr.name = f"Room {i} — {meta.room_type}"
                nr.description = f"{meta.geometry}\nContains: {', '.join(meta.contains)}"
                carve_room(nr)
                connect_rooms(prev, nr)
                rooms.append(nr)
                continue
            break

        rooms.append(placed)

    return Dungeon(width=w, height=h, rooms=rooms, corridors=corridors, doors=doors, grid=grid)
