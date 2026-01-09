from __future__ import annotations
from dataclasses import dataclass
import random
from typing import Optional

@dataclass
class RoomContents:
    encounter: str = ""
    treasure: str = ""
    trap: str = ""
    notes: str = ""

ENCOUNTERS = [
    "2d4 cultists arguing over a map",
    "a lone undead sentinel that remembers its name",
    "3 rival scavengers with a stolen key",
    "a hungry beast chained to an iron ring",
    "a patrol that demands a password",
    "a thing pretending to be a statue",
]

TREASURES = [
    "a pouch of old coin (1d6×10), stamped with a forgotten monarch",
    "a lacquered box containing 1d4 gemstones",
    "a silver ring set with a cloudy opal (whispers faintly at night)",
    "a scroll tube with brittle vellum and a wax seal",
    "a small idol worth 50–200 gp to the right buyer",
    "a potion vial with a cracked label (roll effect)",
]

TRAPS = [
    "pressure plate dart slits (poisoned)",
    "loose flagstone pit (10 ft) with spikes",
    "tripwire bell alarm connected to a nearby room",
    "glyph that bursts with cold when read aloud",
    "ceiling block drop (save or crushed)",
    "oil slick + spark rune (fire)",
]

LOCKS = [
    "simple iron lock (easy)",
    "warded lock with false keyholes (medium)",
    "puzzle latch (requires clue)",
    "arcane seal (requires dispel / keyword)",
]

def generate_room_contents(rng: random.Random, danger: int = 3) -> RoomContents:
    """
    danger: 1..10. Scales intensity lightly.
    """
    # Simple weighted chances you can tune later
    enc_chance = min(0.85, 0.25 + danger * 0.06)
    trp_chance = min(0.70, 0.15 + danger * 0.05)
    tre_chance = min(0.90, 0.30 + danger * 0.05)

    c = RoomContents()
    if rng.random() < enc_chance:
        c.encounter = rng.choice(ENCOUNTERS)
    if rng.random() < tre_chance:
        c.treasure = rng.choice(TREASURES)
    if rng.random() < trp_chance:
        c.trap = rng.choice(TRAPS)

    # Add a little connective tissue
    if c.encounter and rng.random() < 0.25:
        c.notes = "They react strongly if the party carries a visible holy symbol."
    elif c.treasure and rng.random() < 0.25:
        c.notes = "The treasure is marked with a sigil that matches a nearby mural."

    return c

def random_lock(rng: random.Random) -> str:
    return rng.choice(LOCKS)
