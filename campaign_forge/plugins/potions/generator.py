# campaign_forge/plugins/potions/generator.py

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional, Tuple
import json
import math


# ----------------------------
# Data models
# ----------------------------

@dataclass
class Potion:
    name: str
    rarity: str
    absurdity: int  # 0..100
    seed: int
    iteration: int
    # "slots" is the ad-lib assembly. Each slot is a dict with "key"/"label"/"text"/etc.
    slots: Dict[str, Dict[str, Any]]
    # Mechanics summary is structured for exports + future tooling
    mechanics: Dict[str, Any]
    # Pretty rules text for display/scratchpad
    rules_text_md: str
    # Short player-facing blurb
    player_text: str
    # GM notes
    gm_notes: str

    def to_jsonable(self) -> Dict[str, Any]:
        d = asdict(self)
        return d


# ----------------------------
# Starter content tables
# ----------------------------

RARITIES = ["Common", "Uncommon", "Rare", "Very Rare", "Legendary"]

# knobs per rarity: power scale, duration palette, how many complications by default
RARITY_PROFILE = {
    "Common":     {"power": 1.0, "comp_base": 0, "duration_bias": "short"},
    "Uncommon":   {"power": 1.2, "comp_base": 1, "duration_bias": "short"},
    "Rare":       {"power": 1.5, "comp_base": 1, "duration_bias": "mixed"},
    "Very Rare":  {"power": 1.9, "comp_base": 2, "duration_bias": "mixed"},
    "Legendary":  {"power": 2.5, "comp_base": 2, "duration_bias": "long"},
}

# Weighted choice utility
def wchoice(rng, items: List[Tuple[Any, int]]) -> Any:
    total = 0
    for _, w in items:
        total += max(0, int(w))
    if total <= 0:
        return items[0][0]
    roll = rng.randrange(total)
    acc = 0
    for value, w in items:
        w = max(0, int(w))
        acc += w
        if roll < acc:
            return value
    return items[-1][0]


def clamp(n: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, n))


def format_bonus(n: int) -> str:
    return f"+{n}" if n >= 0 else str(n)


# 5e-friendly durations (and a few weird conditional ones)
DURATIONS_SHORT = [
    ("1 minute", 8),
    ("10 minutes", 8),
    ("1 hour", 5),
    ("until the end of your next turn", 5),
    ("until the end of the current combat", 6),
    ("until you take damage", 4),
    ("until you finish a short rest", 2),
]
DURATIONS_MIXED = DURATIONS_SHORT + [
    ("8 hours", 5),
    ("24 hours", 3),
    ("until dawn", 3),
    ("until dusk", 3),
    ("until you speak a lie", 2),
    ("until you willingly drop a weapon", 2),
]
DURATIONS_LONG = DURATIONS_MIXED + [
    ("7 days", 2),
    ("until you are targeted by a divination spell", 1),
    ("permanent until cured", 1),
]

TRIGGERS = [
    ("When you drink it", 14),
    ("When you finish drinking it (as part of the same action)", 8),
    ("The first time you move on your turn after drinking it", 6),
    ("The next time you roll initiative", 6),
    ("When you speak its name aloud", 5),
    ("When the bottle is broken", 5),
    ("When you take fire damage", 3),
    ("When you enter sunlight", 3),
    ("When you touch a door", 3),
    ("At the next dawn", 2),
    ("At the next dusk", 2),
    ("When you tell a deliberate lie", 2),
    ("When you pick up coins worth at least 1 gp", 2),
    ("When you hear music", 2),
    ("When you are reduced below half your hit points", 4),
]

DELIVERY = [
    ("a viscous draught", 8),
    ("a fizzy tonic", 8),
    ("a syrup that clings to the tongue", 7),
    ("a cold gel shot", 6),
    ("a smoky cordial", 5),
    ("a bitter tincture", 6),
    ("a glittering suspension of flakes", 5),
    ("a warm infusion", 5),
    ("a corked vial that hums faintly", 4),
    ("a bottle that is inexplicably heavier on Tuesdays", 1),
]

CONTAINERS = [
    ("Stoppered glass vial", 10),
    ("Wax-sealed bottle with an eye painted on it", 6),
    ("Tiny amphora stamped with an unknown crown", 4),
    ("Bone flask with a hairline crack", 4),
    ("Crystal teardrop that refracts torchlight into runes", 3),
    ("Metal canister that sweats brine", 2),
    ("Paper sachet (yes, it’s a liquid)", 2),
    ("Hollowed-out seashell with a silver clasp", 2),
    ("A bottle that refuses to stand upright", 2),
]

SENSORY = [
    ("smells like rain on hot stone", 6),
    ("tastes like pennies and citrus", 6),
    ("has a minty aftertaste that isn’t there when you think about it", 3),
    ("fizzes with silent bubbles", 5),
    ("casts a faint shadow even in darkness", 3),
    ("leaves your teeth faintly luminescent for an hour", 4),
    ("whispers your name (only you hear it)", 2),
    ("tastes like your least favorite memory", 1),
    ("smells like a library that never existed", 1),
]

# A set of “themes” that bias the effect tables a little
THEMES = [
    ("Vitalist", 8),
    ("Entropic", 8),
    ("Transmutative", 8),
    ("Illusory", 7),
    ("Chronal", 6),
    ("Sympathetic", 6),
    ("Bestial", 6),
    ("Gravitic", 5),
    ("Metamagic", 4),
    ("Domestic", 2),
]

# Targets/scopes
TARGET_SCOPES = [
    ("you (the drinker)", 16),
    ("the next creature you touch within 1 minute", 8),
    ("a creature of your choice you can see within 30 feet", 8),
    ("the nearest creature (other than you) within 30 feet", 5),
    ("a random creature within 30 feet (including you)", 4),
    ("all creatures of your choice within 10 feet", 3),
    ("an object you hold", 3),
    ("a door you can see within 60 feet", 2),
    ("a 10-foot-square of ground you can see within 60 feet", 2),
]

SAVE_TYPES = [
    ("Strength", 4),
    ("Dexterity", 4),
    ("Constitution", 6),
    ("Intelligence", 4),
    ("Wisdom", 6),
    ("Charisma", 4),
]

DAMAGE_TYPES = [
    ("acid", 5),
    ("cold", 5),
    ("fire", 5),
    ("force", 4),
    ("lightning", 5),
    ("necrotic", 5),
    ("poison", 5),
    ("psychic", 4),
    ("radiant", 4),
    ("thunder", 4),
]

CONDITIONS = [
    ("blinded", 3),
    ("charmed", 4),
    ("deafened", 2),
    ("frightened", 4),
    ("grappled", 2),
    ("incapacitated", 2),
    ("invisible", 4),
    ("paralyzed", 2),
    ("poisoned", 4),
    ("prone", 4),
    ("restrained", 3),
    ("stunned", 2),
]

SKILLS = [
    ("Athletics", 4),
    ("Acrobatics", 4),
    ("Stealth", 4),
    ("Perception", 4),
    ("Investigation", 3),
    ("Arcana", 3),
    ("History", 2),
    ("Insight", 3),
    ("Deception", 3),
    ("Intimidation", 2),
    ("Persuasion", 3),
    ("Survival", 3),
    ("Medicine", 2),
    ("Sleight of Hand", 2),
    ("Performance", 2),
    ("Nature", 2),
    ("Religion", 1),
    ("Animal Handling", 1),
]

# ----------------------------
# Effect template library
# ----------------------------

def dc_for(rng, rarity: str, absurdity: int) -> int:
    """
    A reasonable DC band for 5e:
    Common: 11-13
    Uncommon: 12-14
    Rare: 13-15
    Very Rare: 14-16
    Legendary: 15-18
    Absurdity nudges DC slightly.
    """
    base = {
        "Common": 12,
        "Uncommon": 13,
        "Rare": 14,
        "Very Rare": 15,
        "Legendary": 16,
    }[rarity]
    wiggle = rng.randrange(-1, 2)  # -1..+1
    absurd = (absurdity - 50) / 50.0  # -1..+1
    absurd_nudge = int(round(absurd * 1.5))
    return clamp(base + wiggle + absurd_nudge, 10, 20)


def scaled_bonus(rng, rarity: str) -> int:
    """
    Small numeric buffs; keep sane.
    """
    if rarity == "Common":
        return wchoice(rng, [(1, 8), (2, 2)])
    if rarity == "Uncommon":
        return wchoice(rng, [(1, 4), (2, 7), (3, 1)])
    if rarity == "Rare":
        return wchoice(rng, [(2, 5), (3, 6), (4, 1)])
    if rarity == "Very Rare":
        return wchoice(rng, [(2, 2), (3, 6), (4, 3), (5, 1)])
    return wchoice(rng, [(3, 4), (4, 5), (5, 2), (6, 1)])


def scaled_die(rng, rarity: str) -> str:
    """
    Damage/heal dice sized by rarity.
    """
    if rarity == "Common":
        return wchoice(rng, [("1d4", 8), ("1d6", 3)])
    if rarity == "Uncommon":
        return wchoice(rng, [("1d6", 7), ("2d4", 4), ("1d8", 2)])
    if rarity == "Rare":
        return wchoice(rng, [("2d6", 6), ("3d4", 4), ("2d8", 2)])
    if rarity == "Very Rare":
        return wchoice(rng, [("3d6", 5), ("4d4", 4), ("3d8", 3), ("4d6", 1)])
    return wchoice(rng, [("4d6", 4), ("5d6", 3), ("6d4", 3), ("4d8", 2), ("6d6", 1)])


def choose_duration(rng, rarity: str) -> str:
    bias = RARITY_PROFILE[rarity]["duration_bias"]
    if bias == "short":
        return wchoice(rng, DURATIONS_SHORT)
    if bias == "mixed":
        return wchoice(rng, DURATIONS_MIXED)
    return wchoice(rng, DURATIONS_LONG)


# Primary effects are built by selecting a "domain" then a template function.
# Each template returns:
# - rules: str (MD)
# - mechanics: dict (structured)
# - gm_notes: str

def eff_ability_shift(rng, rarity: str, absurdity: int) -> Tuple[str, Dict[str, Any], str]:
    abil = wchoice(rng, SAVE_TYPES)  # ability label
    bonus = scaled_bonus(rng, rarity)
    dur = choose_duration(rng, rarity)
    rules = f"You gain **{format_bonus(bonus)}** to **{abil} checks and {abil} saving throws** for **{dur}**."
    mech = {"type": "ability_bonus", "ability": abil, "bonus": bonus, "duration": dur}
    gm = "Simple, table-light buff. Stack behavior: treat as a bonus of this type; if you prefer, do not stack with similar magic."
    # absurd twist sometimes
    if absurdity >= 60 and rng.randrange(100) < (absurdity - 50):
        other = wchoice(rng, SAVE_TYPES)
        rules += f" **However:** during this time, your **{other}** is *convinced* it is a spice and keeps trying to season your thoughts (disadvantage on the next {other} check you make after each long sentence you speak)."
        mech["quirk"] = {"type": "weird_disadvantage_trigger", "ability": other, "trigger": "long_sentence"}
        gm = "Has a flavorful minor drawback; enforce lightly."
    return rules, mech, gm


def eff_damage_conversion(rng, rarity: str, absurdity: int) -> Tuple[str, Dict[str, Any], str]:
    a = wchoice(rng, DAMAGE_TYPES)
    b = wchoice(rng, DAMAGE_TYPES)
    while b == a:
        b = wchoice(rng, DAMAGE_TYPES)
    dur = choose_duration(rng, rarity)
    rules = f"For **{dur}**, when you deal **{a}** damage, you may choose to have it deal **{b}** damage instead."
    mech = {"type": "damage_convert", "from": a, "to": b, "duration": dur}
    gm = "Very usable and low bookkeeping. If your table worries about resistances, this is strong but fair."
    if absurdity >= 70 and rng.randrange(100) < (absurdity - 60):
        rules += " The damage looks wrong—like it is being remembered rather than happening."
        mech["flavor_tag"] = "remembered_damage"
    return rules, mech, gm


def eff_temp_hp(rng, rarity: str, absurdity: int) -> Tuple[str, Dict[str, Any], str]:
    # temp HP scale
    die = scaled_die(rng, rarity)
    dur = choose_duration(rng, rarity)
    rules = f"You gain **temporary hit points equal to {die}**. They last for **{dur}**."
    mech = {"type": "temp_hp", "amount": die, "duration": dur}
    gm = "Classic. You can roll at drink time. If you prefer deterministic, use average."
    if absurdity >= 55 and rng.randrange(100) < (absurdity - 40):
        rules += " While you have any of these temporary hit points, your shadow occasionally tries to take the hit *for you* (harmless)."
        mech["quirk"] = {"type": "cosmetic_shadow"}
    return rules, mech, gm


def eff_invisibility_weird(rng, rarity: str, absurdity: int) -> Tuple[str, Dict[str, Any], str]:
    dur = wchoice(rng, [
        ("1 minute", 8),
        ("10 minutes", 6),
        ("1 hour", 3),
        ("until you attack or cast a spell", 10),
        ("until you speak a proper noun", 2),
    ])
    rules = f"You become **invisible** for **{dur}**."
    mech = {"type": "condition_gain", "condition": "invisible", "duration": dur}
    gm = "Strong. If rare+, allow; if common/uncommon, prefer the 'until you attack/cast' clause."
    if absurdity >= 60:
        twist = wchoice(rng, [
            ("However, creatures can still see your teeth if you smile.", 3),
            ("However, your carried coins become visible and drift around you like fireflies.", 3),
            ("However, you cast a visible silhouette on solid walls within 5 feet.", 3),
            ("However, you are invisible only to creatures that have eaten in the last hour.", 2),
            ("However, you are invisible only from the waist down.", 1),
        ])
        rules += f" **{twist}**"
        mech["quirk"] = {"type": "invisibility_quirk", "text": twist}
    return rules, mech, gm


def eff_action_economy(rng, rarity: str, absurdity: int) -> Tuple[str, Dict[str, Any], str]:
    dur = choose_duration(rng, rarity)
    pick = wchoice(rng, [
        ("gain", 6),
        ("lose", 4),
        ("warp", 3),
    ])
    if pick == "gain":
        rules = f"For **{dur}**, you gain **one additional reaction** each round (you can’t use more than one reaction per trigger)."
        mech = {"type": "extra_reaction", "count": 1, "duration": dur}
        gm = "Clarify: each reaction still needs its own trigger; no double-Counterspell from one cast."
    elif pick == "lose":
        rules = f"For **{dur}**, you **can’t take bonus actions**."
        mech = {"type": "no_bonus_actions", "duration": dur}
        gm = "Great ‘trade potion’. Keep it simple."
    else:
        rules = f"For **{dur}**, at the start of each of your turns roll a **d6**: on a **1–2** you can only **move**, on a **3–4** you can only **take an action**, on a **5–6** you can do both as normal."
        mech = {"type": "turn_warp", "duration": dur, "die": "d6", "mapping": {"1-2": "move_only", "3-4": "action_only", "5-6": "normal"}}
        gm = "This is disruptive (fun), but it’s a lot. Consider warning in UI as ‘high complexity’."
    if absurdity >= 70 and rng.randrange(100) < (absurdity - 50):
        rules += " The potion seems to negotiate your intent with the universe before allowing the motion."
        mech["flavor_tag"] = "negotiated_actions"
    return rules, mech, gm


def eff_gravity(rng, rarity: str, absurdity: int) -> Tuple[str, Dict[str, Any], str]:
    dur = choose_duration(rng, rarity)
    mode = wchoice(rng, [
        ("light", 6),
        ("heavy", 6),
        ("sideways", 2),
    ])
    if mode == "light":
        rules = f"For **{dur}**, you can **jump triple your normal distance**, and you have **advantage** on checks to resist being **knocked prone**."
        mech = {"type": "gravity_light", "duration": dur, "jump_mult": 3, "adv_vs_prone": True}
        gm = "Mostly harmless; can enable shenanigans. Let it."
    elif mode == "heavy":
        rules = f"For **{dur}**, your speed is **reduced by 10 feet**, and you have **advantage** on checks and saves to resist being **moved** against your will."
        mech = {"type": "gravity_heavy", "duration": dur, "speed_delta": -10, "adv_vs_forced_move": True}
        gm = "Useful defensive tool. Speed reduction is the cost."
    else:
        rules = f"For **{dur}**, gravity **tilts 90 degrees** for you. You can move across walls and ceilings as if they were floors, but you fall if you end your turn without at least one free hand or foot in contact with a surface."
        mech = {"type": "gravity_sideways", "duration": dur}
        gm = "This is extremely fun but can break maps. Be permissive; it’s a potion."
    if absurdity >= 65 and rng.randrange(100) < (absurdity - 45):
        rules += " Tiny objects within 5 feet occasionally orbit you for a second before dropping."
        mech["quirk"] = {"type": "orbiting_trinkets"}
    return rules, mech, gm


def eff_dice_warp(rng, rarity: str, absurdity: int) -> Tuple[str, Dict[str, Any], str]:
    dur = choose_duration(rng, rarity)
    style = wchoice(rng, [
        ("replace", 5),
        ("bank", 5),
        ("swap", 3),
        ("cursed_luck", 3),
    ])
    if style == "replace":
        die = wchoice(rng, [("d12", 5), ("d30", 2), ("d16", 3), ("d10", 2)])
        rules = f"For **{dur}**, the first time each round you roll a **d20**, you may roll a **{die}** instead. (A roll of 1 on the {die} counts as a natural 1.)"
        mech = {"type": "d20_replace", "duration": dur, "replacement": die, "frequency": "1/round"}
        gm = "This is spicy. d30 gets wild; consider reserving for Rare+."
    elif style == "bank":
        rules = f"For **{dur}**, once, when you roll a **d20**, you can **set the result aside** instead of using it. At any later time before the duration ends, you may **replace** a d20 roll with the set-aside result."
        mech = {"type": "banked_roll", "duration": dur, "uses": 1}
        gm = "Players love this. Make sure they track the stored number."
    elif style == "swap":
        rules = f"For **{dur}**, after you see the result of a d20 roll you made, you may **swap** that result with the result of a different d20 roll made by a creature within 30 feet this round (no save). You can do this **once**."
        mech = {"type": "roll_swap", "duration": dur, "range_ft": 30, "uses": 1}
        gm = "This creates stories. It’s strong; keep it limited to once."
    else:
        rules = f"For **{dur}**, you have **advantage** on your next **three** d20 rolls. After the third, you immediately have **disadvantage** on your next **three** d20 rolls."
        mech = {"type": "adv_then_disadv", "duration": dur, "count": 3}
        gm = "Easy to run. Track with checkboxes."
    if absurdity >= 70:
        rules += " The dice feel warm, like they’ve been held too long by someone else."
        mech["flavor_tag"] = "warm_dice"
    return rules, mech, gm


def eff_summon_minor(rng, rarity: str, absurdity: int) -> Tuple[str, Dict[str, Any], str]:
    dur = choose_duration(rng, rarity)
    creature = wchoice(rng, [
        ("a Tiny spectral frog", 5),
        ("a crab made of soap bubbles", 4),
        ("a hovering lantern-moth", 5),
        ("a sarcastic pebble that can speak", 3),
        ("a floating handbell that rings when danger approaches", 4),
        ("a shoelace elemental", 2),
        ("an anxious broom", 2),
    ])
    rules = f"For **{dur}**, you are accompanied by **{creature}**. It is friendly to you, has AC 10 and 1 hit point, and can’t attack. As a **bonus action**, you can command it to perform a simple task (open an unlocked door, carry an item, distract a creature granting you advantage on one Stealth check, etc.)."
    mech = {"type": "utility_companion", "duration": dur, "companion": creature}
    gm = "This is OSR gold: small utility, big creativity."
    if absurdity >= 60 and rng.randrange(100) < (absurdity - 40):
        rules += " If it is reduced to 0 hit points, it explodes into harmless confetti spelling a rude adjective."
        mech["quirk"] = {"type": "confetti_insult"}
    return rules, mech, gm


PRIMARY_EFFECTS = [
    (eff_ability_shift, 10),
    (eff_damage_conversion, 8),
    (eff_temp_hp, 10),
    (eff_invisibility_weird, 7),
    (eff_action_economy, 7),
    (eff_gravity, 7),
    (eff_dice_warp, 7),
    (eff_summon_minor, 6),
]

# Side effects: intended to be resolvable and entertaining.
def side_minor_nuisance(rng, rarity: str, absurdity: int) -> Tuple[str, Dict[str, Any]]:
    nuisance = wchoice(rng, [
        ("your voice becomes slightly too echoey", 5),
        ("your footsteps squeak regardless of footwear", 5),
        ("you smell faintly like onions to beasts", 4),
        ("your hair points toward the nearest exit", 3),
        ("you leave tiny wet handprints on objects you touch", 3),
        ("your reflection blinks one beat late", 2),
        ("your shadow briefly forgets to follow you on stairs", 2),
        ("you can’t stop whispering the last word anyone said", 2),
    ])
    dur = wchoice(rng, [("1 minute", 8), ("10 minutes", 6), ("1 hour", 2)])
    text = f"For **{dur}**, {nuisance}."
    mech = {"type": "nuisance", "duration": dur, "text": nuisance}
    return text, mech


def side_save_or_odd(rng, rarity: str, absurdity: int) -> Tuple[str, Dict[str, Any]]:
    save = wchoice(rng, SAVE_TYPES)
    dc = dc_for(rng, rarity, absurdity)
    odd = wchoice(rng, [
        ("you must speak only in questions", 4),
        ("you believe doors are insults and must apologize before opening one", 3),
        ("you become intensely honest", 3),
        ("you become intensely theatrical", 3),
        ("you cannot willingly step on cracks", 2),
        ("you are convinced your weapon is judging you", 2),
        ("you hear faint applause after every sentence", 2),
        ("you cannot read numbers without tasting metal", 1),
    ])
    dur = wchoice(rng, [("10 minutes", 8), ("1 hour", 4), ("until the end of the current combat", 4)])
    text = f"**Side Effect:** For **{dur}**, make a **DC {dc} {save} saving throw**. On a failure, {odd}."
    mech = {"type": "save_or_behavior", "save": save, "dc": dc, "duration": dur, "effect": odd}
    return text, mech


def side_power_cost(rng, rarity: str, absurdity: int) -> Tuple[str, Dict[str, Any]]:
    cost = wchoice(rng, [
        ("you take 1 level of exhaustion", 2),
        ("you can’t regain hit points from magic until you finish a short rest", 3),
        ("your speed is reduced by 10 feet", 4),
        ("you have disadvantage on the next saving throw you make", 4),
        ("you drop whatever you are holding (no action) when the effect ends", 3),
        ("you can’t speak above a whisper", 3),
        ("you glow dimly out to 10 feet", 4),
    ])
    dur = wchoice(rng, [("until the effect ends", 10), ("for 1 hour", 3)])
    text = f"**Cost:** {cost} **{dur}**."
    mech = {"type": "cost", "duration": dur, "text": cost}
    return text, mech


def side_sympathetic_leak(rng, rarity: str, absurdity: int) -> Tuple[str, Dict[str, Any]]:
    who = wchoice(rng, [
        ("the nearest creature", 5),
        ("a random creature within 30 feet", 4),
        ("a creature that can see you", 4),
        ("your reflection (if visible)", 2),
    ])
    leak = wchoice(rng, [
        ("also gains a weaker version of the primary effect", 5),
        ("takes psychic damage equal to 1d4 when you benefit from the effect", 3),
        ("heals 1d4 hit points when you take damage", 3),
        ("suffers disadvantage on its next attack roll after you succeed on a check", 2),
    ])
    dur = wchoice(rng, [("for the same duration", 10), ("for 1 minute", 4)])
    text = f"**Complication:** For **{dur}**, {who} {leak}."
    mech = {"type": "sympathetic_leak", "duration": dur, "target": who, "leak": leak}
    return text, mech


SIDE_EFFECTS = [
    (side_minor_nuisance, 8),
    (side_save_or_odd, 7),
    (side_power_cost, 7),
    (side_sympathetic_leak, 6),
]

# GM notes helper: suggests complexity
def complexity_rating(mechanics: Dict[str, Any]) -> str:
    t = mechanics.get("primary", {}).get("type", "")
    if t in ("turn_warp", "roll_swap", "gravity_sideways"):
        return "High"
    if t in ("banked_roll", "adv_then_disadv"):
        return "Medium"
    return "Low"


# ----------------------------
# Naming
# ----------------------------

NAME_PREFIX = [
    ("Potion of", 10),
    ("Tonic of", 6),
    ("Draught of", 5),
    ("Elixir of", 7),
    ("Infusion of", 4),
    ("Cordial of", 3),
    ("Philter of", 3),
    ("Suspension of", 2),
]

NAME_NOUN = [
    ("Borrowed Vigor", 8),
    ("Polite Violence", 4),
    ("False Gravity", 6),
    ("Unreasonable Luck", 6),
    ("Moonlit Arson", 3),
    ("Trembling Certainty", 4),
    ("Sideways Intent", 5),
    ("Minor Miracles", 5),
    ("Knotted Time", 4),
    ("Merciful Teeth", 2),
    ("Spiteful Silence", 3),
    ("Second Thoughts", 5),
    ("Sudden Apologies", 2),
    ("Unpaid Debts", 2),
    ("The Frog’s Advice", 1),
]

# Extra spice: optional suffixes that can be applied at high absurdity
NAME_SUFFIX = [
    ("(Do Not Shake)", 3),
    ("(Shake Violently)", 2),
    ("(Not For Internal Use)", 1),
    ("(For External Use Only)", 1),
    ("(Thieves Love This)", 2),
    ("(The Bottle Is Lying)", 1),
    ("(Limited Edition)", 2),
]

# ----------------------------
# Main generation
# ----------------------------

def compute_complications(rng, rarity: str, absurdity: int) -> int:
    base = RARITY_PROFILE[rarity]["comp_base"]
    # absurdity adds more
    # 0..100 -> add about 0..3
    add = 0
    if absurdity >= 35:
        add += 1 if rng.randrange(100) < absurdity else 0
    if absurdity >= 60:
        add += 1 if rng.randrange(100) < (absurdity - 20) else 0
    if absurdity >= 80:
        add += 1 if rng.randrange(100) < (absurdity - 30) else 0
    return clamp(base + add, 0, 4)


def pick_theme(rng) -> str:
    return wchoice(rng, THEMES)


def build_name(rng, absurdity: int) -> str:
    p = wchoice(rng, NAME_PREFIX)
    n = wchoice(rng, NAME_NOUN)
    name = f"{p} {n}"
    if absurdity >= 70 and rng.randrange(100) < (absurdity - 50):
        name += f" {wchoice(rng, NAME_SUFFIX)}"
    return name


def generate_potion(
    rng,
    *,
    rarity: str,
    absurdity: int,
    seed: int,
    iteration: int,
    locks: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Potion:
    """
    locks: slot -> preselected slot dict (so UI can lock & reroll others)
    """
    absurdity = clamp(absurdity, 0, 100)
    locks = locks or {}

    # Slots: identity
    theme = locks.get("theme", {"value": pick_theme(rng)})["value"]
    delivery = locks.get("delivery", {"value": wchoice(rng, DELIVERY)})["value"]
    container = locks.get("container", {"value": wchoice(rng, CONTAINERS)})["value"]
    sensory = locks.get("sensory", {"value": wchoice(rng, SENSORY)})["value"]

    trigger = locks.get("trigger", {"value": wchoice(rng, TRIGGERS)})["value"]
    target = locks.get("target", {"value": wchoice(rng, TARGET_SCOPES)})["value"]
    duration = locks.get("duration", {"value": choose_duration(rng, rarity)})["value"]

    name = locks.get("name", {"value": build_name(rng, absurdity)})["value"]

    # Primary effect
    if "primary" in locks and "rules" in locks["primary"]:
        primary_rules = locks["primary"]["rules"]
        primary_mech = locks["primary"]["mechanics"]
        primary_gm = locks["primary"].get("gm", "")
    else:
        eff_fn = wchoice(rng, PRIMARY_EFFECTS)
        primary_rules, primary_mech, primary_gm = eff_fn(rng, rarity, absurdity)

    # Complications
    complications_n = locks.get("complications_n", {"value": compute_complications(rng, rarity, absurdity)})["value"]

    side_texts: List[str] = []
    side_mechs: List[Dict[str, Any]] = []
    if "side_effects" in locks and isinstance(locks["side_effects"].get("items"), list):
        # locked list
        for it in locks["side_effects"]["items"]:
            side_texts.append(it.get("text", ""))
            side_mechs.append(it.get("mechanics", {}))
    else:
        for _ in range(complications_n):
            side_fn = wchoice(rng, SIDE_EFFECTS)
            t, m = side_fn(rng, rarity, absurdity)
            side_texts.append(t)
            side_mechs.append(m)

    # Assemble text
    # Make it table-usable: a crisp rules block + identity fluff + tags
    player_text = f"**{name}** — {delivery} in a **{container}** that {sensory}."
    player_text += f"\n\n*Theme:* **{theme}**. *Trigger:* **{trigger}**."

    rules_md = f"## {name}\n"
    rules_md += f"*{delivery}; {container}. It {sensory}.*\n\n"
    rules_md += f"**Theme:** {theme}\n\n"
    rules_md += f"**Trigger:** {trigger}\n\n"
    rules_md += f"**Target:** {target}\n\n"
    rules_md += f"**Duration (default):** {duration}\n\n"
    rules_md += f"### Effect\n{primary_rules}\n\n"

    if side_texts:
        rules_md += "### Complications\n"
        for t in side_texts:
            rules_md += f"- {t}\n"
        rules_md += "\n"

    # GM notes: include complexity + “attention warnings”
    comp = complexity_rating({"primary": primary_mech})
    gm_notes = f"Complexity: **{comp}**.\n\n"
    gm_notes += f"Primary GM Notes: {primary_gm}\n\n"
    if side_texts:
        gm_notes += "Complication Notes: These are meant to be enforced consistently but lightly. If a side effect would stall play, convert it to a cosmetic quirk.\n"
    gm_notes += "\n**Table tip:** Put a single index card in front of the player with the Trigger, Duration, and one-line primary effect."

    # Build slots dict for UI (for locking/rerolling)
    slots = {
        "name": {"key": "name", "label": "Name", "value": name},
        "rarity": {"key": "rarity", "label": "Rarity", "value": rarity},
        "absurdity": {"key": "absurdity", "label": "Absurdity", "value": absurdity},
        "theme": {"key": "theme", "label": "Theme", "value": theme},
        "delivery": {"key": "delivery", "label": "Delivery", "value": delivery},
        "container": {"key": "container", "label": "Container", "value": container},
        "sensory": {"key": "sensory", "label": "Sensory", "value": sensory},
        "trigger": {"key": "trigger", "label": "Trigger", "value": trigger},
        "target": {"key": "target", "label": "Target", "value": target},
        "duration": {"key": "duration", "label": "Duration", "value": duration},
        "primary": {"key": "primary", "label": "Primary Effect", "rules": primary_rules, "mechanics": primary_mech, "gm": primary_gm},
        "side_effects": {"key": "side_effects", "label": "Side Effects", "items": [{"text": t, "mechanics": m} for t, m in zip(side_texts, side_mechs)]},
        "complications_n": {"key": "complications_n", "label": "Complications #", "value": complications_n},
    }

    mechanics = {
        "theme": theme,
        "trigger": trigger,
        "target": target,
        "duration_default": duration,
        "primary": primary_mech,
        "side_effects": side_mechs,
        "complexity": comp,
    }

    return Potion(
        name=name,
        rarity=rarity,
        absurdity=absurdity,
        seed=seed,
        iteration=iteration,
        slots=slots,
        mechanics=mechanics,
        rules_text_md=rules_md,
        player_text=player_text,
        gm_notes=gm_notes,
    )


def potion_to_markdown_card(p: Potion) -> str:
    # More compact "card" export for printing
    lines = []
    lines.append(f"# {p.name}")
    lines.append(f"*Rarity:* **{p.rarity}**  |  *Absurdity:* **{p.absurdity}**")
    lines.append("")
    lines.append(f"**Trigger:** {p.slots['trigger']['value']}")
    lines.append(f"**Target:** {p.slots['target']['value']}")
    lines.append(f"**Duration:** {p.slots['duration']['value']}")
    lines.append("")
    lines.append("## Effect")
    lines.append(p.slots["primary"]["rules"])
    if p.slots["side_effects"]["items"]:
        lines.append("")
        lines.append("## Complications")
        for it in p.slots["side_effects"]["items"]:
            lines.append(f"- {it['text']}")
    lines.append("")
    lines.append("---")
    lines.append(f"_Seed:_ `{p.seed}`  |  _Iteration:_ `{p.iteration}`  |  _Theme:_ **{p.slots['theme']['value']}**")
    return "\n".join(lines)


def potion_to_json(p: Potion) -> str:
    return json.dumps(p.to_jsonable(), indent=2, ensure_ascii=False)
