# campaign_forge/plugins/monstergen/tables.py

from __future__ import annotations

# ---- Utility tables for 5e-ish generation ----

CREATURE_TYPES = [
    "Aberration", "Beast", "Celestial", "Construct", "Dragon", "Elemental", "Fey",
    "Fiend", "Giant", "Humanoid", "Monstrosity", "Ooze", "Plant", "Undead",
]

SIZES = ["Tiny", "Small", "Medium", "Large", "Huge", "Gargantuan"]

ALIGNMENTS = [
    "lawful good", "neutral good", "chaotic good",
    "lawful neutral", "neutral", "chaotic neutral",
    "lawful evil", "neutral evil", "chaotic evil",
    "unaligned",
]

ROLES = ["Brute", "Skirmisher", "Artillery", "Controller", "Support", "Solo"]

DAMAGE_TYPES = [
    "bludgeoning", "piercing", "slashing",
    "acid", "cold", "fire", "force", "lightning", "necrotic", "poison", "psychic",
    "radiant", "thunder",
]

CONDITIONS = [
    "blinded", "charmed", "deafened", "frightened", "grappled", "incapacitated",
    "invisible", "paralyzed", "petrified", "poisoned", "prone", "restrained",
    "stunned", "unconscious",
]

SKILLS = [
    "Athletics", "Acrobatics", "Sleight of Hand", "Stealth",
    "Arcana", "History", "Investigation", "Nature", "Religion",
    "Animal Handling", "Insight", "Medicine", "Perception", "Survival",
    "Deception", "Intimidation", "Performance", "Persuasion",
]

SAVES = ["Str", "Dex", "Con", "Int", "Wis", "Cha"]

# ---- 5e proficiency by CR (SRD-consistent style) ----
# CR can be fractional; proficiency depends on CR "band".
def proficiency_for_cr(cr: float) -> int:
    # 5e: +2 up to CR 4, +3 CR 5-8, +4 CR 9-12, +5 CR 13-16, +6 CR 17-20, +7 21-24, +8 25-28, +9 29-30
    if cr <= 4:
        return 2
    if cr <= 8:
        return 3
    if cr <= 12:
        return 4
    if cr <= 16:
        return 5
    if cr <= 20:
        return 6
    if cr <= 24:
        return 7
    if cr <= 28:
        return 8
    return 9

# ---- DMG-style CR tables (simplified but faithful enough for generator balancing) ----
# These are *approximate* bands that match typical DMG guidance:
# Defensive CR uses HP band + AC adjustment.
# Offensive CR uses DPR band + Attack Bonus or Save DC adjustment.
#
# NOTE: This is not a full DMG reproduction; it’s a practical generator approximation.
CR_BANDS = [
    # cr, hp_min, hp_max, ac, dpr_min, dpr_max, atk_bonus, save_dc
    (0,   1,   6,  13,  0,   1,  3,  13),
    (0.125, 7, 35, 13,  2,   3,  3,  13),   # 1/8
    (0.25,  36, 49, 13,  4,   5,  3,  13),   # 1/4
    (0.5,   50, 70, 13,  6,   8,  3,  13),   # 1/2
    (1,     71, 85, 13,  9,  14,  3,  13),
    (2,     86, 100, 13, 15,  20,  3,  13),
    (3,    101, 115, 13, 21,  26,  4,  13),
    (4,    116, 130, 14, 27,  32,  5,  14),
    (5,    131, 145, 15, 33,  38,  6,  15),
    (6,    146, 160, 15, 39,  44,  6,  15),
    (7,    161, 175, 15, 45,  50,  6,  15),
    (8,    176, 190, 16, 51,  56,  7,  16),
    (9,    191, 205, 16, 57,  62,  7,  16),
    (10,   206, 220, 17, 63,  68,  7,  16),
    (11,   221, 235, 17, 69,  74,  8,  17),
    (12,   236, 250, 17, 75,  80,  8,  17),
    (13,   251, 265, 18, 81,  86,  8,  18),
    (14,   266, 280, 18, 87,  92,  8,  18),
    (15,   281, 295, 18, 93,  98,  8,  18),
    (16,   296, 310, 18, 99, 104,  9,  18),
    (17,   311, 325, 19, 105,110, 10,  19),
    (18,   326, 340, 19, 111,116, 10,  19),
    (19,   341, 355, 19, 117,122, 10,  19),
    (20,   356, 400, 19, 123,140, 10,  19),
    (21,   401, 445, 19, 141,158, 11,  20),
    (22,   446, 490, 19, 159,176, 11,  20),
    (23,   491, 535, 19, 177,194, 11,  20),
    (24,   536, 580, 19, 195,212, 12,  21),
    (25,   581, 625, 19, 213,230, 12,  21),
    (26,   626, 670, 19, 231,248, 12,  21),
    (27,   671, 715, 19, 249,266, 13,  22),
    (28,   716, 760, 19, 267,284, 13,  22),
    (29,   761, 805, 19, 285,302, 13,  22),
    (30,   806, 850, 19, 303,320, 14,  23),
]

# Quick lookup helpers
def band_for_hp(hp: int):
    for row in CR_BANDS:
        cr, hp_min, hp_max, ac, dpr_min, dpr_max, atk, dc = row
        if hp_min <= hp <= hp_max:
            return row
    if hp < CR_BANDS[0][1]:
        return CR_BANDS[0]
    return CR_BANDS[-1]

def band_for_dpr(dpr: float):
    for row in CR_BANDS:
        cr, hp_min, hp_max, ac, dpr_min, dpr_max, atk, dc = row
        if dpr_min <= dpr <= dpr_max:
            return row
    if dpr < CR_BANDS[0][4]:
        return CR_BANDS[0]
    return CR_BANDS[-1]

# ---- Archetype knobs ----
ROLE_MODS = {
    "Brute":      {"hp_mult": 1.15, "ac_mod": -1, "dpr_mult": 1.15, "atk_mod": 0, "spd_mod": 0},
    "Skirmisher": {"hp_mult": 0.95, "ac_mod":  1, "dpr_mult": 1.00, "atk_mod": 1, "spd_mod": 10},
    "Artillery":  {"hp_mult": 0.85, "ac_mod":  0, "dpr_mult": 1.20, "atk_mod": 1, "spd_mod": 0},
    "Controller": {"hp_mult": 1.00, "ac_mod":  0, "dpr_mult": 0.95, "atk_mod": 0, "spd_mod": 0},
    "Support":    {"hp_mult": 0.95, "ac_mod":  0, "dpr_mult": 0.90, "atk_mod": 0, "spd_mod": 0},
    "Solo":       {"hp_mult": 1.40, "ac_mod":  1, "dpr_mult": 1.25, "atk_mod": 1, "spd_mod": 0},
}

# A small, SRD-safe set of “generic” traits to spice output while staying system-compatible.
# (No copyrighted monster text; these are original, generic building blocks.)
TRAIT_LIBRARY = [
    {"name": "Keen Senses", "text": "The monster has advantage on Wisdom (Perception) checks that rely on hearing or smell."},
    {"name": "Relentless", "text": "If the monster takes damage that would reduce it to 0 hit points, it is reduced to 1 hit point instead. Once it uses this trait, it can't use it again until it finishes a long rest."},
    {"name": "Magic Resistance", "text": "The monster has advantage on saving throws against spells and other magical effects."},
    {"name": "Pack Coordination", "text": "The monster has advantage on attack rolls against a creature if at least one of the monster’s allies is within 5 feet of the creature and the ally isn’t incapacitated."},
    {"name": "Siege Monster", "text": "The monster deals double damage to objects and structures."},
    {"name": "Amphibious", "text": "The monster can breathe air and water."},
]

REACTION_LIBRARY = [
    {"name": "Deflecting Parry", "text": "The monster adds +2 to its AC against one melee attack that would hit it. To do so, the monster must see the attacker and be wielding a melee weapon or a shield."},
    {"name": "Predatory Reposition", "text": "When a creature the monster can see misses it with an attack, the monster can move up to half its speed without provoking opportunity attacks."},
]

CONTROL_EFFECTS = [
    ("knock prone", "The target must succeed on a Strength saving throw or be knocked prone."),
    ("restrain", "The target must succeed on a Strength saving throw or be restrained until the end of the monster’s next turn."),
    ("frighten", "The target must succeed on a Wisdom saving throw or be frightened of the monster until the end of the target’s next turn."),
    ("poison", "The target must succeed on a Constitution saving throw or be poisoned until the end of the target’s next turn."),
]
