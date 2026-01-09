from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Any
import random
import math


# -----------------------------
# Data model
# -----------------------------

@dataclass
class TrapResult:
    title: str
    intent: str
    type_tags: List[str]
    summary: str
    tells: List[str]
    trigger: str
    delivery: str
    effect: str
    escalation: str
    counterplay: List[str]
    reset: str
    mechanics_5e: str
    osr_notes: str
    seed_used: int
    tags: List[str]

    def to_markdown(self) -> str:
        tags_line = ", ".join(self.tags)
        type_line = ", ".join(self.type_tags)

        md = []
        md.append(f"# {self.title}")
        md.append("")
        md.append(f"**Intent:** {self.intent}")
        md.append(f"**Type:** {type_line}")
        md.append(f"**Tags:** {tags_line}")
        md.append(f"**Seed:** `{self.seed_used}`")
        md.append("")
        md.append("## Quick Summary")
        md.append(self.summary)
        md.append("")
        md.append("## Clues / Tells (Player-Facing)")
        for t in self.tells:
            md.append(f"- {t}")
        md.append("")
        md.append("## The Trap (GM)")
        md.append(f"**Trigger:** {self.trigger}")
        md.append(f"**Delivery:** {self.delivery}")
        md.append(f"**Effect:** {self.effect}")
        md.append(f"**Escalation:** {self.escalation}")
        md.append(f"**Reset / Persistence:** {self.reset}")
        md.append("")
        md.append("## Counterplay (At least 2 ways)")
        for c in self.counterplay:
            md.append(f"- {c}")
        md.append("")
        md.append("## 5e Mechanics Block")
        md.append(self.mechanics_5e)
        md.append("")
        md.append("## OSR Notes")
        md.append(self.osr_notes)
        md.append("")
        return "\n".join(md)


# -----------------------------
# Ad-lib tables
# -----------------------------
# Tables are designed to be:
# - OSR-first: tells + counterplay always generated
# - 5e-compatible: provides DCs, saves, and damage (optional)
# - "Tricks" emphasized: non-damage effects, weird interactions

INTENTS = [
    "Warning Trap",
    "Tax Trap",
    "Control Trap",
    "Narrative Trap",
    "Panic Trap",
    "Punishment Trap",
    "Puzzle Trap",
    "Faction Trap",
]

TRAP_TYPES = [
    ("Mechanical", 4),
    ("Magical", 3),
    ("Environmental", 3),
    ("Psychological", 2),
    ("Living", 2),
    ("Time-Pressure", 2),
    ("Illusion", 2),
    ("Adaptive", 1),
]

# Triggers: always discoverable; include bait/fake triggers
TRIGGERS = [
    "a loose flagstone that sinks with a *soft click*",
    "a taut hair-thin wire at ankle height",
    "opening the {bait_container}",
    "touching the {bait_object}",
    "stepping into the center of the room’s {floor_feature}",
    "crossing an invisible threshold marked by {subtle_marking}",
    "speaking above a whisper (the room *listens*)",
    "bright light (torches/lantern) entering the chamber",
    "removing anything from the {altar_or_plinth}",
    "attempting to force the {door_or_gate}",
    "a delay: {delay_time} after entry",
    "a sequence error: touching {sequence_wrong} before {sequence_right}",
    "a decoy trigger: the obvious {obvious_trigger} does nothing; the real trigger is {real_trigger}",
]

DELIVERIES = [
    "from the ceiling: {ceiling_device}",
    "from the walls: {wall_device}",
    "from the floor: {floor_device}",
    "from the {object_source}: {object_device}",
    "through the air as {air_medium}",
    "as a spreading liquid: {liquid_medium}",
    "as a resonant sound: {sound_medium}",
    "as a faint magical field: {field_medium}",
    "through tiny apertures disguised as {aperture_disguise}",
]

# Effects are built from effect “families” — many are non-damage
EFFECT_FAMILIES = [
    "Restraint/Control",
    "Separation/Isolation",
    "Alarm/Attraction",
    "Debuff/Impairment",
    "Terrain/Environment Shift",
    "Illusion/Misdirection",
    "Resource Tax",
    "Damage (Telegraphed)",
]

EFFECTS = {
    "Restraint/Control": [
        "sticky {goo_type} coats boots and gear; movement becomes {movement_state}",
        "a ring of {locking_material} rises, pinning {target_part} in place",
        "{gravity_anomaly} tugs everyone toward the {pull_direction}",
        "a {net_or_snare} snaps up and {wraps_targets}",
        "the room fills with {sleepy_spores}; eyes grow heavy and reactions slow",
    ],
    "Separation/Isolation": [
        "a slab drops between party members, splitting the room into {split_count} sections",
        "the floor *tilts* and slides, dumping anyone not braced into {drop_zone}",
        "a one-way {barrier_type} seals behind the first creature through",
        "illusory corridors become real for {duration_short}, leading different people different ways",
        "the {bridge_or_path} retracts, leaving only a precarious route across {hazard}",
    ],
    "Alarm/Attraction": [
        "a chorus of {alarm_sound} echoes down the halls; nearby creatures investigate",
        "a visible plume of {smoke_color} vents upward through shafts (guards are alerted)",
        "the trap releases {scent_type}; local predators become curious in {time_window}",
        "runic lights flare and begin pulsing in a pattern used by {faction_signal}",
        "metallic chimes ring in a repeating code: {code_hint}",
    ],
    "Debuff/Impairment": [
        "a burst of {irritant} causes {sense_impairment}",
        "hands go numb as {numbing_agent} settles on skin; fine manipulation becomes difficult",
        "a {curse_style} curse marks the triggering creature with {curse_mark}",
        "the air becomes {air_quality}; breathing is harder and speech is strained",
        "a {memory_glitch} muddles the last {time_amount} of planning",
    ],
    "Terrain/Environment Shift": [
        "{element} floods in from hidden vents; the room becomes {terrain_state}",
        "the temperature swings to {temp_extreme}; metal, stone, and flesh react",
        "motes of {mote_type} reveal and distort lines of sight",
        "the floor becomes {floor_state}; movement changes and falls are likely",
        "the walls exhale {fog_type}, turning angles into uncertain shapes",
    ],
    "Illusion/Misdirection": [
        "a convincing illusion shows {false_scene}; acting on it has consequences",
        "treasure appears where none exists; touching it triggers {secondary_effect}",
        "the exit seems to move; following it leads to {misdirect_destination}",
        "a voice like {voice_source} offers urgent instructions that are {truthiness}",
        "the room ‘relabels’ objects: the {relabel_from} looks exactly like {relabel_to}",
    ],
    "Resource Tax": [
        "corrosive {corrosion_type} eats at {resource_target} unless neutralized quickly",
        "{leeches_or_moths} swarm and attempt to consume {consumable_target}",
        "a siphoning rune drains {resource_stat} until disrupted",
        "a tiny pocket realm ‘collects’ dropped items for {duration_short}",
        "the trap demands a toll: {toll_type} or the effect escalates",
    ],
    "Damage (Telegraphed)": [
        # Telegraphed means: the tell implies the effect strongly.
        "a focused blast of {damage_type} lashes the {danger_zone}",
        "spikes thrust from {spike_source}; the pattern is {pattern_style}",
        "a scything {blade_type} sweeps at {height_band}",
        "a gout of {damage_type} erupts in a rhythm: {rhythm_hint}",
        "a crushing plate descends slowly—fast enough to panic, slow enough to escape",
    ],
}

ESCALATIONS = [
    "If ignored, it repeats every {interval_time} with increasing intensity and louder tells.",
    "Each round it remains active, it expands to include {expansion_target}.",
    "The dungeon ‘learns’: the next time this trap triggers, it adds {extra_layer}.",
    "After {escalation_delay}, it locks exits and forces a choice: endure or solve.",
    "On a second trigger within {time_window}, it upgrades to {escalation_upgrade}.",
    "It creates an opening for nearby creatures: {monster_opportunity}.",
    "It permanently changes the room: {permanent_change}.",
]

RESETS = [
    "One-shot; the mechanism shatters and won’t fire again.",
    "Manual reset by inhabitants (takes {reset_time}); PCs can learn the method.",
    "Auto-reset after {reset_time} if no creatures remain in the room.",
    "Persistent until dispelled or dismantled (it ‘wants’ to stay).",
    "Degrades: each trigger reduces its potency but increases its noise.",
    "Improves: each trigger strengthens the next one (malevolent design).",
]

# Counterplay templates: we will fill 2–4, ensuring at least one tool/fiction solution
COUNTERPLAY = [
    "Spot and avoid the trigger: search for {tell_object} and move with care.",
    "Jam the mechanism with {jam_material} (or wedge it) before triggering it.",
    "Trigger it safely from range using {ranged_method}.",
    "Disarm with tools: {tool_action} at the {mechanism_location}.",
    "Exploit it: lure enemies into the {danger_zone} and set it off.",
    "Bypass via environment: climb/brace along {bypass_surface}.",
    "Magical solution: {spell_like} disrupts the {field_medium}.",
    "Negotiate with it: offer {toll_type} to reduce the effect (works once).",
    "Reverse-engineer: follow the pattern {pattern_style} to cross safely.",
]

TELLS = [
    "Fine {dust_type} outlines seams in the {surface_type}.",
    "A faint smell of {smell_type} lingers near the {object_source}.",
    "Scratches on stone suggest something {movement_hint} recently.",
    "The air is {air_quality} and carries a barely-audible {sound_medium}.",
    "A dead {small_creature} lies near the trigger point, unusually {corpse_detail}.",
    "Hairline cracks radiate from the {floor_feature}.",
    "Runes are {rune_condition}—recently maintained.",
    "A subtle draft pulls toward the {pull_direction}.",
    "Old chalk marks show someone once avoided the {danger_zone}.",
]

# Flavor slots and small vocab
VOCAB = {
    "bait_container": ["jeweled coffer", "rusted strongbox", "velvet-lined reliquary", "stone urn", "sacrificial bowl", "clay idol’s belly-compartment"],
    "bait_object": ["crown", "mirror shard", "silver chalice", "obsidian idol", "bone flute", "golden key"],
    "floor_feature": ["mosaic", "sigil", "spiral inlay", "drain grate", "sunken dais", "checker pattern"],
    "subtle_marking": ["faded salt line", "scratched triangle", "inlaid copper thread", "almost-invisible runes", "oddly clean strip of stone"],
    "altar_or_plinth": ["altar", "plinth", "lectern", "pedestal", "offering table"],
    "door_or_gate": ["door", "portcullis", "stone seal", "bronze hatch"],
    "delay_time": ["3 heartbeats", "10 seconds", "half a minute", "one minute", "two minutes"],
    "sequence_wrong": ["the left candle", "the skull’s eye", "the bronze ring", "the red tile"],
    "sequence_right": ["the center sigil", "the iron latch", "the blue tile", "the hidden notch"],
    "obvious_trigger": ["glowing rune", "big lever", "ominous plate", "spinning wheel"],
    "real_trigger": ["a mundane flagstone", "the second step", "the cold draft line", "the *quiet* corner"],
    "ceiling_device": ["a hinged stone iris", "needle-holes in a carved rose", "a dangling chain with hooks", "a recessed chute", "a hidden sprinkler of powder"],
    "wall_device": ["slits behind a tapestry", "a carved gargoyle mouth", "rotating stone cylinders", "a row of tiny brass nozzles"],
    "floor_device": ["pop-up spikes", "hinged drop-plates", "a pressure bladder", "a concealed turntable", "a hidden suction grate"],
    "object_source": ["statue", "idol", "sarcophagus", "chandelier", "wall relief", "bookshelf"],
    "object_device": ["a pivoting armature", "a spring-loaded needle", "a siphon rune", "a collapsing support", "a nested latch"],
    "air_medium": ["a glittering aerosol", "a heavy sweet vapor", "a stinging mist", "a crawling swarm of motes"],
    "liquid_medium": ["oil-sheen water", "black brine", "alchemical froth", "thin acid drizzle"],
    "sound_medium": ["subsonic hum", "chittering overtone", "keening whistle", "clicking metronome"],
    "field_medium": ["static ward", "gravity knot", "silence bubble", "entropy haze", "binding lattice"],
    "aperture_disguise": ["mortar gaps", "decorative rosettes", "false rivets", "hairline cracks"],
    "goo_type": ["resin", "tar", "sap", "alchemical glue", "fungal slime"],
    "movement_state": ["halved movement", "difficult terrain", "a stuck-and-drag crawl", "clumsy stomps"],
    "locking_material": ["iron", "bone", "rootwood", "glass", "salt-crystal"],
    "target_part": ["ankles", "wrists", "backpacks", "weapons", "shields"],
    "gravity_anomaly": ["a sudden sideways gravity shift", "a brief weightlessness", "a heavy downward pull", "a lurching inversion"],
    "pull_direction": ["ceiling", "east wall", "center dais", "drain"],
    "net_or_snare": ["chain-net", "thorn snare", "wire lattice", "weighted net"],
    "wraps_targets": ["pins arms to sides", "entangles legs", "snags packs and weapons", "hoists targets slightly off the ground"],
    "sleepy_spores": ["pale spores", "gold dust", "lavender pollen", "grey fungal smoke"],
    "split_count": ["two", "three", "four"],
    "drop_zone": ["a lower chamber", "a flooded pit", "a spiked trench (visible!)", "a crawlspace full of bones"],
    "barrier_type": ["force wall", "iron grate", "stone slab", "glass partition"],
    "duration_short": ["30 seconds", "1 minute", "3 rounds", "10 rounds"],
    "bridge_or_path": ["stone bridge", "rope walkway", "mosaic path", "bone arch"],
    "hazard": ["a deep shaft", "a roaring furnace trench", "a pool of brackish water", "a nest of biting insects"],
    "alarm_sound": ["metal chimes", "a gong tone", "mocking laughter", "a shrill pipe-note"],
    "smoke_color": ["blue", "green", "black", "silver", "purple"],
    "scent_type": ["blood-sweet musk", "ripe fruit odor", "ozone tang", "wet fur stench"],
    "time_window": ["2 minutes", "5 minutes", "10 minutes"],
    "faction_signal": ["cultists", "goblins", "city watch", "dwarven wardens", "necromancer thralls"],
    "code_hint": ["short-short-long", "a rising triple tone", "a stuttering rhythm", "a single note repeating every breath"],
    "irritant": ["pepper dust", "lime powder", "itching spores", "glass-fine sand"],
    "sense_impairment": ["watering eyes (disadvantage on Perception)", "coughing fits", "temporary ringing ears", "blurred vision"],
    "numbing_agent": ["cold mist", "tingling oil", "pale static", "stinging nettle vapor"],
    "curse_style": ["minor", "ancient", "spiteful", "contract-like"],
    "curse_mark": ["a black handprint", "a glowing eye sigil", "a faint chain motif", "a halo of frost"],
    "air_quality": ["too dry", "damp and heavy", "thin", "ionized", "peppery"],
    "memory_glitch": ["illusory déjà vu", "momentary confusion", "misplaced certainty"],
    "time_amount": ["minute", "hour", "day"],
    "element": ["water", "sand", "steam", "ash", "beetles", "vine tendrils"],
    "terrain_state": ["slick", "wading-deep", "knee-high churn", "a crawling carpet", "a choking haze"],
    "temp_extreme": ["freezing", "scalding", "fever-hot", "bone-cold"],
    "mote_type": ["phosphorescent dust", "black soot", "silver flakes", "floating spores"],
    "floor_state": ["like ice", "like a treadmill", "slightly elastic", "suddenly uneven", "tilted at an angle"],
    "fog_type": ["white fog", "greenish mist", "inky darkness-fog", "shimmering heat-haze"],
    "false_scene": ["a pit where none exists", "a collapsing ceiling", "a friend in distress", "an exit that looks safe", "a monster charging"],
    "secondary_effect": ["a loud alarm", "a binding rune", "a spray of irritant", "a sudden floor shift"],
    "misdirect_destination": ["a dead end with a second trap", "an occupied guard room", "a looping corridor", "a flooded cul-de-sac"],
    "voice_source": ["a trusted ally", "a parent’s voice", "a kindly priest", "the party’s patron", "a sobbing child"],
    "truthiness": ["half-true", "tempting but wrong", "true but incomplete", "a deliberate lie"],
    "relabel_from": ["rusty lever", "plain door", "stone idol", "rope bridge"],
    "relabel_to": ["golden lever", "secret door", "priceless statue", "safe walkway"],
    "corrosion_type": ["salt-spray", "rust bloom", "acid mist", "mildew rot"],
    "resource_target": ["ropes", "lockpicks", "weapons", "armor straps", "spell component pouch"],
    "leeches_or_moths": ["tiny moths", "paper-eating beetles", "greedy mites", "leech-sprays"],
    "consumable_target": ["rations", "scrolls", "torches", "arrows", "bandages"],
    "resource_stat": ["spell slots (lowest available)", "hit dice", "ammo", "light sources", "a random potion"],
    "toll_type": ["a coin", "a drop of blood", "a spoken secret", "a memory (minor)", "a vow"],
    "damage_type": ["fire", "cold", "lightning", "acid", "necrotic", "poison"],
    "danger_zone": ["center tiles", "near the altar", "the entry corridor", "the far corner"],
    "spike_source": ["the floor", "the walls", "a rising plate", "a collapsing step"],
    "pattern_style": ["in a checker pattern", "in a spiral", "in alternating rows", "only where shadows fall"],
    "blade_type": ["pendulum blade", "scything bar", "spinning fan-blade", "wire garrote-sweep"],
    "height_band": ["waist height", "knee height", "neck height (telegraphed!)", "ankle height"],
    "rhythm_hint": ["one-two-pause", "a steady heartbeat", "a stutter-step cadence", "a slow rising tempo"],
    "interval_time": ["6 seconds", "1 round", "10 seconds", "30 seconds"],
    "expansion_target": ["adjacent squares", "doorways", "the ceiling space", "any metal objects"],
    "extra_layer": ["a secondary alarm", "a locking seal", "a lingering curse mark", "a harsher environment effect"],
    "escalation_delay": ["1 minute", "3 rounds", "30 seconds"],
    "escalation_upgrade": ["a stronger save DC", "double area", "a second effect family", "a persistent hazard"],
    "monster_opportunity": ["a hidden murder-hole opens", "a patrol arrives", "a lair beast wakes", "a guardian is released"],
    "permanent_change": ["the room becomes difficult terrain", "the door seals until solved", "the altar cracks, revealing lore", "a new passage opens (risky)"],
    "reset_time": ["1 minute", "10 minutes", "1 hour", "until dawn"],
    "tell_object": ["seams", "runes", "wire", "fresh oil", "odd scratch marks"],
    "jam_material": ["pitons", "coins", "wax", "cloth", "a dagger", "chalk and water paste"],
    "ranged_method": ["a 10-foot pole", "a tossed stone", "a mage hand", "an arrow with twine"],
    "tool_action": ["careful prying", "bracing a wedge", "cutting the correct wire", "unscrewing a plate"],
    "mechanism_location": ["north wall panel", "base of the statue", "under the threshold", "behind the tapestry"],
    "bypass_surface": ["ceiling beams", "wall ledge", "statue backs", "chain-hung rafters"],
    "spell_like": ["dispel magic", "mage hand", "gust", "shape water", "minor illusion"],
    "dust_type": ["chalk dust", "ash", "pollen", "salt crystals"],
    "surface_type": ["floor", "threshold", "wall panel", "altar base"],
    "smell_type": ["ozone", "lamp oil", "vinegar", "sweet rot", "iron"],
    "movement_hint": ["slides", "retracts", "swings", "drops"],
    "small_creature": ["rat", "bat", "snake", "lizard"],
    "corpse_detail": ["flattened", "desiccated", "frosted over", "covered in glittering dust"],
}

# Intent weighting nudges families and type tags.
INTENT_WEIGHTS = {
    "Warning Trap": {"Damage (Telegraphed)": 1, "Alarm/Attraction": 2, "Illusion/Misdirection": 2, "Terrain/Environment Shift": 2, "Restraint/Control": 2, "Resource Tax": 1, "Debuff/Impairment": 1, "Separation/Isolation": 1},
    "Tax Trap": {"Resource Tax": 4, "Debuff/Impairment": 2, "Alarm/Attraction": 1, "Restraint/Control": 2, "Terrain/Environment Shift": 1, "Illusion/Misdirection": 1, "Damage (Telegraphed)": 1, "Separation/Isolation": 1},
    "Control Trap": {"Restraint/Control": 4, "Separation/Isolation": 3, "Terrain/Environment Shift": 2, "Alarm/Attraction": 1, "Illusion/Misdirection": 1, "Debuff/Impairment": 1, "Resource Tax": 1, "Damage (Telegraphed)": 1},
    "Narrative Trap": {"Illusion/Misdirection": 4, "Debuff/Impairment": 2, "Terrain/Environment Shift": 2, "Alarm/Attraction": 1, "Restraint/Control": 1, "Resource Tax": 1, "Damage (Telegraphed)": 1, "Separation/Isolation": 1},
    "Panic Trap": {"Alarm/Attraction": 4, "Separation/Isolation": 3, "Terrain/Environment Shift": 2, "Debuff/Impairment": 2, "Restraint/Control": 2, "Illusion/Misdirection": 1, "Resource Tax": 1, "Damage (Telegraphed)": 1},
    "Punishment Trap": {"Damage (Telegraphed)": 3, "Debuff/Impairment": 2, "Restraint/Control": 2, "Resource Tax": 2, "Alarm/Attraction": 1, "Terrain/Environment Shift": 1, "Illusion/Misdirection": 1, "Separation/Isolation": 1},
    "Puzzle Trap": {"Illusion/Misdirection": 3, "Restraint/Control": 3, "Terrain/Environment Shift": 2, "Separation/Isolation": 2, "Debuff/Impairment": 1, "Resource Tax": 1, "Alarm/Attraction": 1, "Damage (Telegraphed)": 1},
    "Faction Trap": {"Alarm/Attraction": 2, "Restraint/Control": 2, "Resource Tax": 2, "Debuff/Impairment": 2, "Terrain/Environment Shift": 2, "Damage (Telegraphed)": 1, "Separation/Isolation": 2, "Illusion/Misdirection": 1},
}


# -----------------------------
# Helpers
# -----------------------------

def _wchoice(rng: random.Random, items: List[Tuple[Any, int]]) -> Any:
    total = sum(w for _, w in items)
    pick = rng.uniform(0, total)
    acc = 0.0
    for v, w in items:
        acc += w
        if pick <= acc:
            return v
    return items[-1][0]


def _fill(template: str, rng: random.Random) -> str:
    # Very small templater: replaces {key} with a random choice from VOCAB[key]
    out = template
    # Repeat passes so nested braces are handled if any (we keep it simple).
    for _ in range(3):
        start = out.find("{")
        if start == -1:
            break
        end = out.find("}", start + 1)
        if end == -1:
            break
        key = out[start + 1 : end].strip()
        if key in VOCAB:
            rep = rng.choice(VOCAB[key])
        else:
            rep = f"<{key}>"
        out = out[:start] + rep + out[end + 1 :]
    return out


def _choose_effect_family(intent: str, rng: random.Random) -> str:
    weights = INTENT_WEIGHTS.get(intent)
    if not weights:
        return rng.choice(EFFECT_FAMILIES)
    weighted = [(fam, max(1, int(weights.get(fam, 1)))) for fam in EFFECT_FAMILIES]
    return _wchoice(rng, weighted)


def _dc_by_difficulty(base: int, difficulty: int) -> int:
    # difficulty 0..4 → small DC adjustment
    # 0 easy, 1 normal, 2 spicy, 3 hard, 4 brutal
    return max(10, min(22, base + [ -2, 0, 2, 4, 6 ][difficulty]))


def _damage_by_tier(rng: random.Random, lethality: int, tier: int) -> str:
    """
    lethality 0..4, tier 1..4 (rough dungeon depth / party tier)
    returns dice string.
    OSR note: even "brutal" stays somewhat bounded; consequences do the heavy lifting.
    """
    # base dice by tier
    # tier1: 1d6, tier2: 2d6, tier3: 4d6, tier4: 6d6 (telegraphed)
    base = {1: (1, 6), 2: (2, 6), 3: (4, 6), 4: (6, 6)}.get(tier, (2, 6))
    n, d = base
    # lethality scales dice count a bit
    n = max(1, n + [0, 0, 1, 2, 3][lethality])
    # occasionally use d8 for higher lethality
    if lethality >= 3 and rng.random() < 0.25:
        d = 8
    return f"{n}d{d}"


def _mechanics_block(
    rng: random.Random,
    trap_type: str,
    intent: str,
    lethality: int,
    complexity: int,
    tier: int,
    has_damage: bool,
) -> str:
    # 5e mechanics: Perception/Investigation to notice; Thieves' Tools/Arcana to disable; save type
    base_notice = 13
    base_disable = 14
    base_save = 13

    dc_notice = _dc_by_difficulty(base_notice, complexity)
    dc_disable = _dc_by_difficulty(base_disable, complexity)
    dc_save = _dc_by_difficulty(base_save, lethality if has_damage else max(0, lethality - 1))

    save = rng.choice(["Dexterity", "Constitution", "Wisdom", "Strength", "Intelligence"])
    skill_notice = rng.choice(["Perception", "Investigation"])
    skill_disable = "Thieves' Tools" if trap_type == "Mechanical" else rng.choice(["Arcana", "Thieves' Tools", "Religion"])

    lines = []
    lines.append(f"- **Detect:** DC {dc_notice} {skill_notice} to spot the tell(s) before triggering.")
    lines.append(f"- **Disable:** DC {dc_disable} {skill_disable} (or a clever fictional solution) to prevent activation.")
    lines.append(f"- **Trigger:** When triggered, affected creatures make a **DC {dc_save} {save} save**.")
    if has_damage:
        dmg = _damage_by_tier(rng, lethality, tier)
        lines.append(f"- **On Fail:** Take **{dmg}** damage (type depends on the trap) and suffer the listed complication.")
        lines.append(f"- **On Success:** Half damage (or avoid the worst complication) and keep moving.")
    else:
        lines.append(f"- **On Fail:** Suffer the listed condition/complication (damage is minimal or none).")
        lines.append(f"- **On Success:** Reduce the effect, avoid the worst part, or gain an advantage to counterplay.")

    # OSR-lean knobs: emphasize tells and solutions
    lines.append(f"- **OSR Lean:** Players who describe specific precautions should gain advantage, automatic success, or avoid the save entirely.")
    return "\n".join(lines)


def _osr_notes(intent: str, has_damage: bool) -> str:
    notes = []
    notes.append("- Treat this as a *situation*, not a button: reward probing, bracing, mapping, and caution.")
    notes.append("- Ensure the tells are presented **before** the trap is sprung if the party is moving carefully.")
    notes.append("- Offer at least one “no-roll” solution (wedge it, bypass it, trigger from afar, etc.).")
    if has_damage:
        notes.append("- Damage is intentionally telegraphed; the real danger is the complication/escalation and dungeon response.")
    else:
        notes.append("- Even without damage, the trap should create pressure: noise, time loss, separation, or resource drain.")
    if intent in ("Faction Trap", "Narrative Trap"):
        notes.append("- Make the trap *make sense* in-world: who built it, what behavior does it shape, who can bypass it?")
    return "\n".join(notes)


# -----------------------------
# Main generator
# -----------------------------

def generate_trap(
    rng: random.Random,
    *,
    intent: str,
    lethality: int,
    complexity: int,
    tier: int,
    magic_vs_mech: int,
    weirdness: int,
    reset_style: str,
    include_damage: str,
    context_tags: Optional[List[str]] = None,
    seed_used: int = 0,
) -> TrapResult:
    """
    magic_vs_mech: 0..100 (higher => more magical)
    weirdness: 0..100 (higher => more surreal effects)
    include_damage: "Never"|"Sometimes"|"Often"
    reset_style: "Any" or one of reset labels
    """

    # Trap type
    t_items = TRAP_TYPES[:]
    # Nudge toward magical/mechanical based on slider
    if magic_vs_mech >= 60:
        t_items = [(("Magical"), 6), (("Mechanical"), 2), (("Environmental"), 3), (("Illusion"), 3), (("Adaptive"), 1), (("Living"), 1), (("Psychological"), 2), (("Time-Pressure"), 2)]
    elif magic_vs_mech <= 40:
        t_items = [(("Mechanical"), 6), (("Environmental"), 4), (("Magical"), 2), (("Illusion"), 1), (("Adaptive"), 1), (("Living"), 2), (("Psychological"), 2), (("Time-Pressure"), 2)]
    else:
        # balanced
        t_items = TRAP_TYPES + [("Mechanical", 1), ("Magical", 1)]

    trap_type = _wchoice(rng, t_items)
    type_tags = [trap_type]

    # Effect family influenced by intent and weirdness
    family = _choose_effect_family(intent, rng)
    if weirdness >= 70 and rng.random() < 0.25:
        # nudge into illusion/environment
        family = rng.choice(["Illusion/Misdirection", "Terrain/Environment Shift", "Debuff/Impairment"])

    effect_template = rng.choice(EFFECTS[family])
    effect = _fill(effect_template, rng)

    # Damage presence
    if include_damage == "Never":
        has_damage = False
    elif include_damage == "Often":
        has_damage = True if family == "Damage (Telegraphed)" else (rng.random() < 0.35)
    else:  # Sometimes
        has_damage = True if family == "Damage (Telegraphed)" else (rng.random() < 0.15)

    if family == "Damage (Telegraphed)":
        type_tags.append("Telegraphed Damage")
        has_damage = True if include_damage != "Never" else False

    trigger = _fill(rng.choice(TRIGGERS), rng)
    delivery = _fill(rng.choice(DELIVERIES), rng)

    # Tells: always 2-4, scaled with complexity (more complex = more subtle, but still present)
    tell_count = 2 + (1 if complexity >= 2 else 0) + (1 if rng.random() < 0.35 else 0)
    tells = [_fill(rng.choice(TELLS), rng) for _ in range(tell_count)]
    # Ensure at least one very concrete tell
    if rng.random() < 0.5:
        tells[0] = "The mechanism is *physically present*: you can see " + _fill("fine {dust_type} outlining seams in the {surface_type}.", rng)

    escalation = _fill(rng.choice(ESCALATIONS), rng)

    # Reset
    reset_candidates = RESETS
    if reset_style != "Any":
        # crude filter: include those containing the keyword
        filt = [r for r in RESETS if reset_style.lower().split()[0] in r.lower()]
        if filt:
            reset_candidates = filt
    reset = _fill(rng.choice(reset_candidates), rng)

    # Counterplay: ensure at least two; include one “fiction/tool” and one “skill/mechanics-ish”
    cp = []
    cp_templates = COUNTERPLAY[:]
    rng.shuffle(cp_templates)

    for tpl in cp_templates:
        s = _fill(tpl, rng)
        # keep it varied; avoid too many “Magical solution” if not magical
        if "Magical solution" in s and trap_type not in ("Magical", "Illusion"):
            if rng.random() < 0.7:
                continue
        cp.append(s)
        if len(cp) >= (2 + (1 if complexity >= 2 else 0) + (1 if rng.random() < 0.2 else 0)):
            break

    if len(cp) < 2:
        cp.append("Back off, reassess, and interact with the environment: wedge, brace, bypass, or trigger from afar.")

    # Summary: single-paragraph “at the table” pitch
    summary_bits = [
        f"A {trap_type.lower()} trap that triggers when {trigger}.",
        f"It manifests {delivery} and causes {effect}.",
        f"It escalates: {escalation}",
    ]
    if has_damage:
        summary_bits.append("It can hurt, but it’s designed to be avoidable if players heed the tells.")
    else:
        summary_bits.append("The real threat is pressure and consequences rather than raw damage.")
    summary = " ".join(summary_bits)

    # Title: mash a noun + vibe
    vibe = rng.choice(["Whispering", "Hollow", "Greedy", "Crooked", "Sorrowful", "Mirror", "Thorn", "Clockwork", "Oathbound", "Hungry"])
    noun = rng.choice(["Threshold", "Idol", "Dais", "Latch", "Mosaic", "Plinth", "Gate", "Chapel", "Vault", "Hall"])
    title = f"The {vibe} {noun}"

    mechanics_5e = _mechanics_block(
        rng=rng,
        trap_type=trap_type if trap_type != "Illusion" else "Magical",
        intent=intent,
        lethality=lethality,
        complexity=complexity,
        tier=tier,
        has_damage=has_damage,
    )
    osr = _osr_notes(intent, has_damage)

    # Tags
    tags = ["Trap", "TricksAndTraps", f"Trap:{trap_type}", f"Trap:Intent:{intent.replace(' ', '')}"]
    if has_damage:
        tags.append("Trap:Damage")
    else:
        tags.append("Trap:NoDamage")
    tags.append(f"Trap:Lethality:{lethality}")
    tags.append(f"Trap:Complexity:{complexity}")
    tags.append(f"Trap:Tier:{tier}")
    if context_tags:
        tags.extend(context_tags)

    return TrapResult(
        title=title,
        intent=intent,
        type_tags=type_tags,
        summary=summary,
        tells=tells,
        trigger=trigger,
        delivery=delivery,
        effect=effect,
        escalation=escalation,
        counterplay=cp,
        reset=reset,
        mechanics_5e=mechanics_5e,
        osr_notes=osr,
        seed_used=seed_used,
        tags=tags,
    )
