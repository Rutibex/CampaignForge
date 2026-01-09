# campaign_forge/plugins/monstergen/generator.py

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
import math

from .tables import (
    CREATURE_TYPES, SIZES, ALIGNMENTS, ROLES, DAMAGE_TYPES, CONDITIONS, SKILLS, SAVES,
    proficiency_for_cr, CR_BANDS, ROLE_MODS,
    band_for_hp, band_for_dpr,
    TRAIT_LIBRARY, REACTION_LIBRARY, CONTROL_EFFECTS
)


# ----------------------------
# Data models
# ----------------------------

@dataclass
class MonsterAttack:
    name: str
    kind: str  # "Melee Weapon Attack", "Ranged Weapon Attack", "Melee or Ranged Weapon Attack"
    to_hit: int
    reach_or_range: str
    target: str
    damage: str
    rider: str = ""


@dataclass
class MonsterAbility:
    name: str
    text: str
    category: str = "Trait"  # Trait / Action / Bonus Action / Reaction / Legendary Action / Lair Action


@dataclass
class Monster:
    name: str
    size: str
    creature_type: str
    alignment: str
    ac: int
    hp: int
    hit_dice: str
    speed: str
    stats: Dict[str, int]  # STR DEX CON INT WIS CHA
    saves: Dict[str, int] = field(default_factory=dict)
    skills: Dict[str, int] = field(default_factory=dict)
    senses: str = ""
    languages: str = ""
    cr: str = "1"
    xp: int = 200
    proficiency_bonus: int = 2
    damage_resistances: str = ""
    damage_immunities: str = ""
    condition_immunities: str = ""
    vulnerabilities: str = ""
    traits: List[MonsterAbility] = field(default_factory=list)
    actions: List[MonsterAbility] = field(default_factory=list)
    reactions: List[MonsterAbility] = field(default_factory=list)
    legendary_actions: List[MonsterAbility] = field(default_factory=list)

    # For CR audit (GM-facing)
    audit: Dict[str, str] = field(default_factory=dict)

    def ability_mod(self, score: int) -> int:
        return (score - 10) // 2


# ----------------------------
# Helpers
# ----------------------------

def clamp(n, a, b):
    return max(a, min(b, n))

def choose(rng, seq):
    return seq[rng.randrange(0, len(seq))]

def chance(rng, p: float) -> bool:
    return rng.random() < p

def fmt_signed(n: int) -> str:
    return f"+{n}" if n >= 0 else str(n)

def avg_die(die: int) -> float:
    return (die + 1) / 2.0

def xp_for_cr(cr: float) -> int:
    # Standard 5e XP table (common reference). Using a typical mapping.
    # This is stable enough for a generator; exactness is not mission-critical.
    table = {
        0: 10, 0.125: 25, 0.25: 50, 0.5: 100,
        1: 200, 2: 450, 3: 700, 4: 1100, 5: 1800,
        6: 2300, 7: 2900, 8: 3900, 9: 5000, 10: 5900,
        11: 7200, 12: 8400, 13: 10000, 14: 11500, 15: 13000,
        16: 15000, 17: 18000, 18: 20000, 19: 22000, 20: 25000,
        21: 33000, 22: 41000, 23: 50000, 24: 62000, 25: 75000,
        26: 90000, 27: 105000, 28: 120000, 29: 135000, 30: 155000,
    }
    # snap to nearest key
    keys = sorted(table.keys(), key=lambda x: abs(x - cr))
    return table[keys[0]]

def cr_label(cr: float) -> str:
    if cr == 0.125:
        return "1/8"
    if cr == 0.25:
        return "1/4"
    if cr == 0.5:
        return "1/2"
    if float(cr).is_integer():
        return str(int(cr))
    return str(cr)

def parse_cr_label(label: str) -> float:
    label = str(label).strip()
    if label == "1/8":
        return 0.125
    if label == "1/4":
        return 0.25
    if label == "1/2":
        return 0.5
    try:
        return float(label)
    except Exception:
        return 1.0

def ability_scores_for_role(rng, cr: float, role: str) -> Dict[str, int]:
    # Role-driven stat tendencies + CR scaling.
    # We generate "reasonable" monster arrays; GM can edit after.
    base = 10 + int(cr * 0.35)  # mild scaling
    role_bias = {
        "Brute":      {"Str": 3, "Con": 3, "Dex": -1, "Int": -1},
        "Skirmisher": {"Dex": 3, "Str": 1, "Con": 1, "Wis": 1},
        "Artillery":  {"Dex": 2, "Int": 3, "Wis": 1, "Con": -1},
        "Controller": {"Wis": 3, "Int": 2, "Dex": 1, "Str": -1},
        "Support":    {"Wis": 3, "Cha": 2, "Con": 1, "Str": -1},
        "Solo":       {"Con": 3, "Str": 2, "Dex": 1, "Wis": 1},
    }.get(role, {})

    stats = {k: base for k in ["Str", "Dex", "Con", "Int", "Wis", "Cha"]}

    for k, delta in role_bias.items():
        stats[k] += delta

    # Add randomness, but keep in a sane range. Higher CR can exceed 20.
    cap = 20 if cr <= 10 else 24 if cr <= 20 else 26
    floor = 6 if cr <= 1 else 8

    for k in stats:
        stats[k] += rng.randint(-2, 2)
        stats[k] = clamp(stats[k], floor, cap)

    # Make sure the "primary" stats feel primary.
    for _ in range(2):
        k = choose(rng, list(role_bias.keys())) if role_bias else choose(rng, list(stats.keys()))
        stats[k] = clamp(stats[k] + rng.randint(1, 3), floor, cap)

    return stats

def suggested_speed(rng, creature_type: str, role: str) -> str:
    base = 30
    if creature_type in ("Beast", "Fey"):
        base = 40 if chance(rng, 0.35) else 30
    if creature_type in ("Construct", "Ooze"):
        base = 20 if chance(rng, 0.6) else 30
    if creature_type in ("Dragon", "Fiend", "Celestial"):
        base = 40 if chance(rng, 0.4) else 30

    spd_mod = ROLE_MODS.get(role, {}).get("spd_mod", 0)
    walk = clamp(base + spd_mod, 10, 60)

    modes = []
    if chance(rng, 0.25) and creature_type not in ("Ooze",):
        modes.append(f"climb {clamp(walk, 10, 60)} ft.")
    if chance(rng, 0.20) and creature_type in ("Beast", "Elemental", "Fiend", "Dragon", "Celestial", "Fey"):
        modes.append(f"fly {clamp(walk + 10, 20, 80)} ft.")
    if chance(rng, 0.18) and creature_type in ("Beast", "Elemental", "Ooze", "Plant"):
        modes.append(f"swim {clamp(walk, 10, 60)} ft.")
    if chance(rng, 0.10) and creature_type in ("Elemental", "Undead"):
        modes.append(f"burrow {clamp(walk - 10, 10, 40)} ft.")

    if modes:
        return f"{walk} ft., " + ", ".join(modes)
    return f"{walk} ft."

def hit_dice_for_size(size: str) -> int:
    return {
        "Tiny": 4, "Small": 6, "Medium": 8, "Large": 10, "Huge": 12, "Gargantuan": 20
    }.get(size, 8)

def compute_hp_and_ac(rng, target_cr: float, role: str) -> Tuple[int, int]:
    # Start from CR band center and apply role mods
    # Find closest CR band row to target_cr
    row = min(CR_BANDS, key=lambda r: abs(r[0] - target_cr))
    cr, hp_min, hp_max, base_ac, dpr_min, dpr_max, atk, dc = row
    hp_center = int((hp_min + hp_max) / 2)
    hp = int(hp_center * ROLE_MODS[role]["hp_mult"])
    hp = int(hp * rng.uniform(0.90, 1.10))
    hp = max(1, hp)

    ac = base_ac + ROLE_MODS[role]["ac_mod"] + rng.randint(-1, 1)
    ac = clamp(ac, 10, 22)
    return hp, ac

def compute_target_dpr(rng, target_cr: float, role: str) -> float:
    row = min(CR_BANDS, key=lambda r: abs(r[0] - target_cr))
    dpr = (row[4] + row[5]) / 2.0
    dpr *= ROLE_MODS[role]["dpr_mult"]
    dpr *= rng.uniform(0.90, 1.10)
    return max(0.0, dpr)

def expected_attack_bonus(target_cr: float) -> int:
    row = min(CR_BANDS, key=lambda r: abs(r[0] - target_cr))
    return row[6]

def expected_save_dc(target_cr: float) -> int:
    row = min(CR_BANDS, key=lambda r: abs(r[0] - target_cr))
    return row[7]

def pick_saves_and_skills(rng, stats: Dict[str, int], prof: int, creature_type: str, role: str):
    # Choose 1-3 saves and 2-4 skills.
    save_count = 1 if role in ("Support", "Artillery") else 2
    if role == "Solo":
        save_count = 3

    # Bias saves by type
    save_bias = {
        "Undead": ["Wis", "Con"],
        "Dragon": ["Dex", "Con", "Wis"],
        "Fiend": ["Wis", "Cha"],
        "Fey": ["Dex", "Wis"],
        "Construct": ["Con", "Wis"],
        "Beast": ["Dex", "Con"],
        "Humanoid": ["Dex", "Wis"],
    }.get(creature_type, ["Dex", "Con"])

    saves = {}
    for _ in range(save_count):
        s = choose(rng, save_bias) if chance(rng, 0.7) else choose(rng, SAVES)
        mod = (stats[s] - 10) // 2
        saves[s] = mod + prof

    # Skills
    skill_count = 2 + (1 if chance(rng, 0.35) else 0) + (1 if role == "Solo" else 0)
    # Rough mapping of skills to abilities
    skill_ability = {
        "Athletics": "Str",
        "Acrobatics": "Dex",
        "Sleight of Hand": "Dex",
        "Stealth": "Dex",
        "Arcana": "Int",
        "History": "Int",
        "Investigation": "Int",
        "Nature": "Int",
        "Religion": "Int",
        "Animal Handling": "Wis",
        "Insight": "Wis",
        "Medicine": "Wis",
        "Perception": "Wis",
        "Survival": "Wis",
        "Deception": "Cha",
        "Intimidation": "Cha",
        "Performance": "Cha",
        "Persuasion": "Cha",
    }

    skills = {}
    for _ in range(skill_count):
        sk = choose(rng, SKILLS)
        abil = skill_ability[sk]
        mod = (stats[abil] - 10) // 2
        # Some monsters have expertise-ish bumps; keep modest
        bump = prof if chance(rng, 0.15) else 0
        skills[sk] = mod + prof + bump

    return saves, skills

def senses_and_languages(rng, creature_type: str, stats: Dict[str, int]) -> Tuple[str, str]:
    parts = []
    # Darkvision common for many types
    if creature_type in ("Undead", "Fiend", "Fey", "Aberration", "Monstrosity", "Dragon", "Elemental") and chance(rng, 0.75):
        parts.append("darkvision 60 ft.")
    if chance(rng, 0.15):
        parts.append("blindsight 10 ft.")
    if creature_type in ("Ooze", "Elemental") and chance(rng, 0.2):
        parts.append("tremorsense 30 ft.")
    if chance(rng, 0.05):
        parts.append("truesight 30 ft.")

    wis_mod = (stats["Wis"] - 10) // 2
    passive = 10 + wis_mod + (2 if chance(rng, 0.4) else 0)
    senses = ", ".join(parts) + (", " if parts else "") + f"passive Perception {passive}"

    # Languages
    if creature_type in ("Beast", "Ooze", "Plant"):
        langs = "—"
    else:
        options = ["Common", "Dwarvish", "Elvish", "Goblin", "Infernal", "Abyssal", "Draconic", "Celestial", "Sylvan", "Undercommon"]
        count = 1 + (1 if chance(rng, 0.35) else 0)
        langs = ", ".join(sorted(set(choose(rng, options) for _ in range(count))))
        if chance(rng, 0.2):
            langs += "; telepathy 60 ft."
    return senses, langs

def choose_defenses(rng, creature_type: str, cr: float) -> Tuple[str, str, str, str]:
    # Keep modest; high CR gets more toys.
    resist = []
    immune = []
    cond_immune = []
    vuln = []

    if creature_type == "Undead":
        if chance(rng, 0.4): resist.append("necrotic")
        if chance(rng, 0.25): immune.append("poison")
        if chance(rng, 0.5): cond_immune.append("poisoned")
    elif creature_type == "Fiend":
        if chance(rng, 0.5): resist.append("fire")
        if chance(rng, 0.25): resist.append("cold")
    elif creature_type == "Elemental":
        if chance(rng, 0.5): immune.append(choose(rng, ["poison", "fire", "cold", "lightning"]))
        if chance(rng, 0.25): cond_immune.append("poisoned")
    elif creature_type == "Construct":
        if chance(rng, 0.5): immune.append("poison")
        if chance(rng, 0.6): cond_immune += ["poisoned", "charmed", "exhaustion"]
    elif creature_type == "Ooze":
        if chance(rng, 0.4): immune.append("acid")
        if chance(rng, 0.6): cond_immune += ["blinded", "charmed", "deafened", "frightened", "prone"]
    elif creature_type == "Dragon":
        if chance(rng, 0.85): immune.append(choose(rng, ["fire", "cold", "lightning", "poison", "acid"]))

    # CR gate: avoid heavy immunity stacks at low CR
    if cr <= 2:
        immune = immune[:1]
        cond_immune = cond_immune[:2]
    if cr <= 5:
        resist = resist[:2]
        immune = immune[:1]

    # stringify
    return (
        ", ".join(resist),
        ", ".join(immune),
        ", ".join(sorted(set(cond_immune))),
        ", ".join(vuln),
    )

def make_attack_suite(rng, target_cr: float, role: str, stats: Dict[str, int], prof: int) -> Tuple[List[MonsterAttack], float, int, int]:
    """
    Returns: attacks, dpr_estimate, attack_bonus, save_dc
    """
    dpr_target = compute_target_dpr(rng, target_cr, role)
    exp_atk = expected_attack_bonus(target_cr) + ROLE_MODS[role]["atk_mod"]
    save_dc = expected_save_dc(target_cr)

    # Choose whether this monster attacks via weapon attacks or forced saves (controller)
    prefers_save = (role in ("Controller", "Support")) and chance(rng, 0.6)

    # Attack bonus derived from primary stat + prof, then nudged toward expected.
    primary = "Str" if role in ("Brute",) else "Dex" if role in ("Skirmisher", "Artillery") else "Wis" if role in ("Controller", "Support") else "Str"
    mod = (stats[primary] - 10) // 2
    to_hit = mod + prof
    # Nudge toward expected; keep within +/-2
    if to_hit < exp_atk:
        to_hit = min(exp_atk, to_hit + rng.randint(1, 2))
    elif to_hit > exp_atk + 2:
        to_hit = max(exp_atk, to_hit - rng.randint(1, 2))

    # Build 1-2 attacks, plus multiattack text as an action.
    attacks: List[MonsterAttack] = []
    damage_type = choose(rng, ["slashing", "piercing", "bludgeoning"] + DAMAGE_TYPES)
    if prefers_save:
        # "Spell-like" action with a save rider contributes to DPR
        # We'll represent as an "Action" rather than "Attack" in statblock.
        # But we still return DPR estimate.
        return attacks, dpr_target, to_hit, save_dc

    # Determine number of swings
    swings = 1
    if target_cr >= 5 and chance(rng, 0.7):
        swings = 2
    if target_cr >= 11 and chance(rng, 0.5):
        swings = 3

    # Split DPR across swings
    per_swing = max(1.0, dpr_target / swings)

    # Convert per_swing average to dice expression, loosely.
    # We'll choose a base die by role.
    die = 8
    if role == "Brute":
        die = 10
    elif role == "Skirmisher":
        die = 8
    elif role == "Artillery":
        die = 8

    # Determine number of dice so average ~= per_swing - mod
    # avg(die) * n + mod ~= per_swing
    avg = avg_die(die)
    n = max(1, int(round((per_swing - max(0, mod)) / avg)))
    n = clamp(n, 1, 6)

    # Recompute achieved
    achieved = avg * n + max(0, mod)
    # Small tweak: add +2 or +3 flat if still low at higher CR
    flat = 0
    if achieved < per_swing * 0.9 and target_cr >= 5:
        flat = rng.choice([2, 3])

    dmg_expr = f"{n}d{die} {fmt_signed(max(0, mod) + flat)}"
    dmg_str = f"{dmg_expr} {damage_type} damage"

    reach = "5 ft."
    if role in ("Brute", "Solo") and chance(rng, 0.35):
        reach = "10 ft."

    attacks.append(MonsterAttack(
        name=choose(rng, ["Claw", "Bite", "Slam", "Glaive", "Scything Talon", "Warped Strike"]),
        kind="Melee Weapon Attack",
        to_hit=to_hit,
        reach_or_range=f"reach {reach}",
        target="one target",
        damage=dmg_str,
        rider="",
    ))

    # Optionally add a ranged attack for artillery
    if role == "Artillery" and chance(rng, 0.65):
        # make weaker but ranged
        r_die = 6
        r_avg = avg_die(r_die)
        r_n = max(1, int(round((per_swing * 0.8 - max(0, mod)) / r_avg)))
        r_n = clamp(r_n, 1, 8)
        r_expr = f"{r_n}d{r_die} {fmt_signed(max(0, mod))}"
        r_dmg = f"{r_expr} {choose(rng, DAMAGE_TYPES)} damage"
        attacks.append(MonsterAttack(
            name=choose(rng, ["Shard Bolt", "Barbed Javelin", "Spine Volley", "Void Needle"]),
            kind="Ranged Weapon Attack",
            to_hit=to_hit,
            reach_or_range="range 60/180 ft.",
            target="one target",
            damage=r_dmg,
            rider="",
        ))

    # DPR estimate: just target (we tuned around it)
    return attacks, dpr_target, to_hit, save_dc

def build_actions_from_attacks(rng, attacks: List[MonsterAttack], target_cr: float, role: str, save_dc: int, dpr_target: float) -> List[MonsterAbility]:
    actions: List[MonsterAbility] = []

    if attacks:
        # Make Multiattack if more than 1 swing implied at higher CR
        swings = 1
        if target_cr >= 5 and chance(rng, 0.7):
            swings = 2
        if target_cr >= 11 and chance(rng, 0.5):
            swings = max(swings, 3)

        if swings >= 2:
            names = []
            # Prefer first attack name repeated
            names.append(attacks[0].name)
            if len(attacks) > 1 and chance(rng, 0.35):
                names.append(attacks[1].name)
            # Build a simple multiattack statement
            if len(names) == 1:
                text = f"The monster makes {swings} {names[0].lower()} attacks."
            else:
                # e.g., two claw attacks and one bolt
                parts = [f"{max(1, swings-1)} {names[0].lower()} attack{'s' if swings-1 != 1 else ''}", f"one {names[1].lower()} attack"]
                text = "The monster makes " + " and ".join(parts) + "."
            actions.append(MonsterAbility(name="Multiattack", text=text, category="Action"))

        # Add each attack as an action line
        for atk in attacks:
            rider = f" {atk.rider}".rstrip()
            line = (
                f"{atk.kind}: +{atk.to_hit} to hit, {atk.reach_or_range}, {atk.target}. "
                f"Hit: {atk.damage}.{rider}"
            )
            actions.append(MonsterAbility(name=atk.name, text=line, category="Action"))

    else:
        # Save-based / controller action
        effect_name, effect_text = choose(rng, CONTROL_EFFECTS)
        # Convert DPR into an AoE-ish burst with half on save (typical)
        # We'll choose dice so average ~ dpr_target
        die = 8 if target_cr >= 5 else 6
        avg = avg_die(die)
        n = max(2, int(round(dpr_target / avg)))
        n = clamp(n, 2, 12)
        dmg_type = choose(rng, DAMAGE_TYPES)
        dmg_expr = f"{n}d{die}"
        text = (
            f"The monster targets one creature it can see within 60 feet. "
            f"The target must make a DC {save_dc} saving throw. "
            f"On a failed save, the target takes {dmg_expr} {dmg_type} damage, and it must also {effect_text} "
            f"On a successful save, the target takes half as much damage and suffers no additional effect."
        )
        actions.append(MonsterAbility(name=choose(rng, ["Warp Hex", "Binding Pulse", "Mind-Splinter", "Grasping Surge"]), text=text, category="Action"))

    # Recharge breath/beam for dragons/solos at higher CR (optional)
    if role in ("Solo",) and target_cr >= 8 and chance(rng, 0.5):
        die = 10
        avg = avg_die(die)
        n = clamp(int(round((dpr_target * 1.25) / avg)), 6, 18)
        dmg_type = choose(rng, DAMAGE_TYPES)
        text = (
            f"The monster exhales destructive force in a 30-foot cone. "
            f"Each creature in that area must make a DC {save_dc} Dexterity saving throw, "
            f"taking {n}d{die} {dmg_type} damage on a failed save, or half as much damage on a successful one."
        )
        actions.append(MonsterAbility(name="Devastating Exhale (Recharge 5–6)", text=text, category="Action"))

    return actions

def maybe_add_traits(rng, creature_type: str, role: str, cr: float) -> Tuple[List[MonsterAbility], List[MonsterAbility]]:
    traits: List[MonsterAbility] = []
    reactions: List[MonsterAbility] = []

    # Baseline number of traits
    count = 1 + (1 if chance(rng, 0.5) else 0) + (1 if role == "Solo" else 0)

    # Ensure thematic picks
    pool = list(TRAIT_LIBRARY)
    if creature_type in ("Fiend", "Fey", "Undead", "Dragon") and chance(rng, 0.4):
        traits.append(MonsterAbility(name="Innate Magic", text="The monster’s attacks are magical for the purpose of overcoming resistance and immunity to nonmagical attacks.", category="Trait"))

    for _ in range(count):
        t = choose(rng, pool)
        traits.append(MonsterAbility(name=t["name"], text=t["text"], category="Trait"))

    # Reactions are rarer at low CR
    if cr >= 3 and chance(rng, 0.35):
        r = choose(rng, REACTION_LIBRARY)
        reactions.append(MonsterAbility(name=r["name"], text=r["text"], category="Reaction"))

    # Condition immunities sometimes deserve a trait explanation
    return traits, reactions

def estimate_defensive_cr(hp: int, ac: int) -> Tuple[float, str]:
    band = band_for_hp(hp)
    base_cr = float(band[0])
    expected_ac = band[3]
    # DMG-style: every 2 AC above/below shifts CR by 1 (approx)
    delta = ac - expected_ac
    shift = int(math.floor(delta / 2))
    adj_cr = clamp(base_cr + shift, 0, 30)
    note = f"HP {hp} ⇒ base DCR {cr_label(base_cr)} (band {band[1]}–{band[2]}), AC {ac} vs expected {expected_ac} ⇒ shift {shift:+d}"
    return float(adj_cr), note

def estimate_offensive_cr(dpr: float, attack_bonus: int, save_dc: int, uses_save: bool) -> Tuple[float, str]:
    band = band_for_dpr(dpr)
    base_cr = float(band[0])
    expected_atk = band[6]
    expected_dc = band[7]
    if uses_save:
        delta = save_dc - expected_dc
    else:
        delta = attack_bonus - expected_atk
    shift = int(math.floor(delta / 2))  # every 2 points ~ 1 CR shift
    adj_cr = clamp(base_cr + shift, 0, 30)
    which = f"DC {save_dc} vs {expected_dc}" if uses_save else f"+{attack_bonus} vs +{expected_atk}"
    note = f"DPR {dpr:.1f} ⇒ base OCR {cr_label(base_cr)} (band {band[4]}–{band[5]}), {which} ⇒ shift {shift:+d}"
    return float(adj_cr), note

def finalize_cr(dcr: float, ocr: float) -> float:
    return float(clamp((dcr + ocr) / 2.0, 0, 30))

def random_name(rng, creature_type: str, role: str) -> str:
    adj = ["Ashen", "Gutter", "Gleaming", "Wretched", "Umbral", "Verdant", "Howling", "Sable", "Ivory", "Rime", "Scorch", "Grim"]
    nouns = ["Stalker", "Husk", "Marauder", "Seer", "Behemoth", "Warden", "Reaver", "Sentinel", "Mireling", "Skirmisher", "Oracle", "Devourer"]
    type_tag = creature_type.lower()
    core = f"{choose(rng, adj)} {choose(rng, nouns)}"
    if chance(rng, 0.35):
        core = f"{core} of the {choose(rng, ['Deep', 'Hollow', 'Iron', 'Thorn', 'Wyrd', 'Cinder'])}"
    if chance(rng, 0.25):
        core = f"{core} ({type_tag})"
    return core

def generate_monster(rng, target_cr: float, role: str, creature_type: str, size: str, alignment: str, name: Optional[str] = None) -> Monster:
    prof = proficiency_for_cr(target_cr)

    stats = ability_scores_for_role(rng, target_cr, role)
    hp, ac = compute_hp_and_ac(rng, target_cr, role)

    # Hit dice approximation: hp ≈ n * (avg die + Con mod)
    hd = hit_dice_for_size(size)
    con_mod = (stats["Con"] - 10) // 2
    per_die_avg = avg_die(hd) + con_mod
    n_dice = max(1, int(round(hp / max(1.0, per_die_avg))))
    hit_dice = f"{n_dice}d{hd} {fmt_signed(n_dice * con_mod)}"

    speed = suggested_speed(rng, creature_type, role)

    saves, skills = pick_saves_and_skills(rng, stats, prof, creature_type, role)
    senses, languages = senses_and_languages(rng, creature_type, stats)

    resist, immune, cond_immune, vuln = choose_defenses(rng, creature_type, target_cr)

    attacks, dpr_est, atk_bonus, save_dc = make_attack_suite(rng, target_cr, role, stats, prof)
    uses_save = (len(attacks) == 0)
    actions = build_actions_from_attacks(rng, attacks, target_cr, role, save_dc, dpr_est)

    traits, reactions = maybe_add_traits(rng, creature_type, role, target_cr)

    # CR audit
    dcr, dcr_note = estimate_defensive_cr(hp, ac)
    ocr, ocr_note = estimate_offensive_cr(dpr_est, atk_bonus, save_dc, uses_save)
    final = finalize_cr(dcr, ocr)

    mon = Monster(
        name=name or random_name(rng, creature_type, role),
        size=size,
        creature_type=creature_type,
        alignment=alignment,
        ac=ac,
        hp=hp,
        hit_dice=hit_dice,
        speed=speed,
        stats=stats,
        saves=saves,
        skills=skills,
        senses=senses,
        languages=languages,
        cr=cr_label(final),
        xp=xp_for_cr(final),
        proficiency_bonus=proficiency_for_cr(final),
        damage_resistances=resist,
        damage_immunities=immune,
        condition_immunities=cond_immune,
        vulnerabilities=vuln,
        traits=traits,
        actions=actions,
        reactions=reactions,
        legendary_actions=[],
        audit={
            "target_cr": cr_label(target_cr),
            "defensive_cr": cr_label(dcr),
            "offensive_cr": cr_label(ocr),
            "final_cr": cr_label(final),
            "dcr_note": dcr_note,
            "ocr_note": ocr_note,
            "uses_save": "yes" if uses_save else "no",
            "dpr_est": f"{dpr_est:.1f}",
            "attack_bonus": str(atk_bonus),
            "save_dc": str(save_dc),
        },
    )

    # Add legendary actions for Solo at higher CR
    if role == "Solo" and parse_cr_label(mon.cr) >= 10:
        mon.legendary_actions = [
            MonsterAbility(
                name="Legendary Actions",
                text="The monster can take 3 legendary actions, choosing from the options below. Only one legendary action option can be used at a time and only at the end of another creature’s turn. The monster regains spent legendary actions at the start of its turn.",
                category="Legendary Header"
            ),
            MonsterAbility(name="Swift Step", text="The monster moves up to half its speed without provoking opportunity attacks.", category="Legendary Action"),
            MonsterAbility(name="Punishing Strike", text="The monster makes one attack.", category="Legendary Action"),
            MonsterAbility(name="Ruinous Glare (Costs 2 Actions)", text=f"One creature the monster can see within 60 feet must succeed on a DC {expected_save_dc(final)} Wisdom saving throw or be frightened until the end of its next turn.", category="Legendary Action"),
        ]

    return mon

def monster_to_markdown(mon: Monster) -> str:
    # 5e style markdown block. Compatible with scratchpad + export.
    # This is “statblock-like” without relying on proprietary formatting.
    lines = []
    lines.append(f"## {mon.name}")
    lines.append(f"*{mon.size} {mon.creature_type.lower()}, {mon.alignment}*")
    lines.append("")
    lines.append(f"**Armor Class** {mon.ac}")
    lines.append(f"**Hit Points** {mon.hp} ({mon.hit_dice})")
    lines.append(f"**Speed** {mon.speed}")
    lines.append("")
    lines.append("|STR|DEX|CON|INT|WIS|CHA|")
    lines.append("|---:|---:|---:|---:|---:|---:|")
    s = mon.stats
    def cell(k):
        m = (s[k]-10)//2
        return f"{s[k]} ({fmt_signed(m)})"
    lines.append(f"|{cell('Str')}|{cell('Dex')}|{cell('Con')}|{cell('Int')}|{cell('Wis')}|{cell('Cha')}|")
    lines.append("")

    if mon.saves:
        lines.append("**Saving Throws** " + ", ".join(f"{k} {fmt_signed(v)}" for k, v in mon.saves.items()))
    if mon.skills:
        lines.append("**Skills** " + ", ".join(f"{k} {fmt_signed(v)}" for k, v in mon.skills.items()))
    if mon.vulnerabilities:
        lines.append("**Damage Vulnerabilities** " + mon.vulnerabilities)
    if mon.damage_resistances:
        lines.append("**Damage Resistances** " + mon.damage_resistances)
    if mon.damage_immunities:
        lines.append("**Damage Immunities** " + mon.damage_immunities)
    if mon.condition_immunities:
        lines.append("**Condition Immunities** " + mon.condition_immunities)
    if mon.senses:
        lines.append("**Senses** " + mon.senses)
    if mon.languages:
        lines.append("**Languages** " + mon.languages)
    lines.append(f"**Challenge** {mon.cr} ({mon.xp} XP)  **Proficiency Bonus** {fmt_signed(mon.proficiency_bonus)}")
    lines.append("")

    if mon.traits:
        lines.append("### Traits")
        for t in mon.traits:
            lines.append(f"**{t.name}.** {t.text}")
        lines.append("")

    if mon.actions:
        lines.append("### Actions")
        for a in mon.actions:
            lines.append(f"**{a.name}.** {a.text}")
        lines.append("")

    if mon.reactions:
        lines.append("### Reactions")
        for r in mon.reactions:
            lines.append(f"**{r.name}.** {r.text}")
        lines.append("")

    if mon.legendary_actions:
        lines.append("### Legendary Actions")
        for la in mon.legendary_actions:
            if la.category == "Legendary Header":
                lines.append(la.text)
            else:
                lines.append(f"**{la.name}.** {la.text}")
        lines.append("")

    # CR audit panel at bottom (GM-facing, optional)
    lines.append("---")
    lines.append("### CR Audit (Generator)")
    lines.append(f"- Target CR: **{mon.audit.get('target_cr','?')}**")
    lines.append(f"- Defensive CR: **{mon.audit.get('defensive_cr','?')}** — {mon.audit.get('dcr_note','')}")
    lines.append(f"- Offensive CR: **{mon.audit.get('offensive_cr','?')}** — {mon.audit.get('ocr_note','')}")
    lines.append(f"- Final CR: **{mon.audit.get('final_cr','?')}**")
    lines.append(f"- DPR estimate: **{mon.audit.get('dpr_est','?')}**, Uses save-based offense: **{mon.audit.get('uses_save','?')}**, Attack bonus: **+{mon.audit.get('attack_bonus','?')}**, Save DC: **{mon.audit.get('save_dc','?')}**")

    return "\n".join(lines)
