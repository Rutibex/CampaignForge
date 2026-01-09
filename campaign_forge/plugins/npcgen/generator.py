from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple



# ---------------------------
# 5e Ability Score Helpers
# ---------------------------

ABILITIES = ("STR", "DEX", "CON", "INT", "WIS", "CHA")

def _mod(score: int) -> int:
    return (int(score) - 10) // 2

def roll_ability_scores(rng: random.Random) -> Dict[str, int]:
    """Roll 6 ability scores using 4d6 drop lowest; assign randomly."""
    scores: List[int] = []
    for _ in range(6):
        rolls = [rng.randint(1, 6) for __ in range(4)]
        rolls.sort()
        scores.append(sum(rolls[1:]))  # drop the lowest die
    rng.shuffle(scores)
    return {abil: scores[i] for i, abil in enumerate(ABILITIES)}

def ability_block_md(stats: Dict[str, int]) -> str:
    parts: List[str] = []
    for abil in ABILITIES:
        sc = int(stats.get(abil, 10))
        m = _mod(sc)
        sign = "+" if m >= 0 else ""
        parts.append(f"{abil} {sc} ({sign}{m})")
    return " | ".join(parts)

# ---------------------------
# 5e-ish Combat Stat Helpers
# ---------------------------

POWER_TIERS = ("Common", "Standard", "Veteran", "Elite")

# A small, practical set of class templates (not full PC rules).
CLASS_TEMPLATES: Dict[str, Dict[str, Any]] = {
    "Fighter": {"hit_die": 10, "save_profs": ("STR", "CON"), "armor": "heavy", "shield": True, "weapons": "martial", "caster": None},
    "Rogue":   {"hit_die": 8,  "save_profs": ("DEX", "INT"), "armor": "light", "shield": False, "weapons": "simple+martial", "caster": None},
    "Ranger":  {"hit_die": 10, "save_profs": ("STR", "DEX"), "armor": "medium", "shield": False, "weapons": "martial", "caster": "primal"},
    "Cleric":  {"hit_die": 8,  "save_profs": ("WIS", "CHA"), "armor": "medium", "shield": True, "weapons": "simple", "caster": "divine"},
    "Wizard":  {"hit_die": 6,  "save_profs": ("INT", "WIS"), "armor": "none", "shield": False, "weapons": "simple", "caster": "arcane"},
    "Warlock": {"hit_die": 8,  "save_profs": ("WIS", "CHA"), "armor": "light", "shield": False, "weapons": "simple", "caster": "arcane"},
    "Bard":    {"hit_die": 8,  "save_profs": ("DEX", "CHA"), "armor": "light", "shield": False, "weapons": "simple+martial", "caster": "arcane"},
    "Paladin": {"hit_die": 10, "save_profs": ("WIS", "CHA"), "armor": "heavy", "shield": True, "weapons": "martial", "caster": "divine"},
}

ROLE_CLASS_WEIGHTS: Dict[str, List[Tuple[str, int]]] = {
    "Merchant": [("Bard", 3), ("Rogue", 2), ("Fighter", 1)],
    "Cultist":  [("Warlock", 3), ("Cleric", 2), ("Rogue", 1)],
    "Officer":  [("Fighter", 3), ("Paladin", 2), ("Ranger", 1)],
    "Guard":    [("Fighter", 3), ("Ranger", 1), ("Paladin", 1)],
    "Priest":   [("Cleric", 4), ("Paladin", 1)],
    "Scholar":  [("Wizard", 4), ("Bard", 1)],
    "Thief":    [("Rogue", 4), ("Bard", 1), ("Ranger", 1)],
    "Hunter":   [("Ranger", 4), ("Fighter", 1)],
    "Mercenary":[("Fighter", 4), ("Rogue", 1), ("Ranger", 1)],
}

ARMOR_CHOICES = {
    "none":   [("No armor", 0)],
    "light":  [("Leather armor", 11), ("Studded leather", 12)],
    "medium": [("Hide armor", 12), ("Chain shirt", 13), ("Scale mail", 14)],
    "heavy":  [("Chain mail", 16), ("Splint armor", 17), ("Plate armor", 18)],
}

WEAPONS = {
    "melee_simple": [("Club", "1d4"), ("Mace", "1d6"), ("Spear", "1d6"), ("Handaxe", "1d6")],
    "melee_martial": [("Longsword", "1d8"), ("Battleaxe", "1d8"), ("Warhammer", "1d8"), ("Glaive", "1d10")],
    "ranged_simple": [("Sling", "1d4"), ("Light crossbow", "1d8"), ("Shortbow", "1d6")],
    "ranged_martial": [("Longbow", "1d8"), ("Heavy crossbow", "1d10")],
}

ARCANE_CANTRIPS = ["Arcane Bolt", "Frost Shard", "Spark", "Minor Illusion", "Mage Hand"]
DIVINE_CANTRIPS = ["Radiant Spark", "Sacred Flame", "Guidance", "Thaumaturgy"]
PRIMAL_CANTRIPS = ["Thorn Whip", "Stone Dart", "Primal Flame", "Druidcraft"]

ARCANE_SPELLS_1 = ["Shield", "Magic Missile", "Sleep", "Burning Hands", "Charm Person"]
ARCANE_SPELLS_2 = ["Misty Step", "Hold Person", "Invisibility", "Scorching Ray"]
ARCANE_SPELLS_3 = ["Fireball", "Counterspell", "Haste", "Fear"]

DIVINE_SPELLS_1 = ["Bless", "Cure Wounds", "Command", "Sanctuary"]
DIVINE_SPELLS_2 = ["Lesser Restoration", "Spiritual Weapon", "Hold Person"]
DIVINE_SPELLS_3 = ["Revivify", "Spirit Guardians", "Dispel Magic"]

PRIMAL_SPELLS_1 = ["Entangle", "Cure Wounds", "Fog Cloud", "Hunter's Mark"]
PRIMAL_SPELLS_2 = ["Pass without Trace", "Spike Growth", "Flame Blade"]
PRIMAL_SPELLS_3 = ["Call Lightning", "Plant Growth", "Wind Wall"]

def _weighted_choice(rng: random.Random, items: List[Tuple[str, int]]) -> str:
    total = sum(w for _, w in items)
    if total <= 0:
        return items[0][0]
    roll = rng.randint(1, total)
    acc = 0
    for v, w in items:
        acc += w
        if roll <= acc:
            return v
    return items[-1][0]

def _power_to_level(power: str, rng: random.Random) -> int:
    p = (power or "Standard").strip().title()
    if p == "Common":
        return rng.randint(1, 2)
    if p == "Veteran":
        return rng.randint(4, 6)
    if p == "Elite":
        return rng.randint(7, 9)
    return rng.randint(2, 4)

def proficiency_bonus(level: int) -> int:
    level = max(1, int(level))
    return 2 + (level - 1) // 4

def _pick_class_for_role(rng: random.Random, role: str) -> str:
    role = (role or "").strip()
    weights = ROLE_CLASS_WEIGHTS.get(role)
    if not weights:
        # fallback: plausible generalist
        weights = [("Fighter", 3), ("Rogue", 2), ("Cleric", 1), ("Ranger", 1), ("Wizard", 1)]
    return _weighted_choice(rng, weights)

def _spell_lists_for(tradition: str):
    tradition = (tradition or "").lower()
    if tradition == "divine":
        return DIVINE_CANTRIPS, DIVINE_SPELLS_1, DIVINE_SPELLS_2, DIVINE_SPELLS_3
    if tradition == "primal":
        return PRIMAL_CANTRIPS, PRIMAL_SPELLS_1, PRIMAL_SPELLS_2, PRIMAL_SPELLS_3
    return ARCANE_CANTRIPS, ARCANE_SPELLS_1, ARCANE_SPELLS_2, ARCANE_SPELLS_3

def generate_combat_profile(npc: Dict[str, Any], cfg: "NpcGenConfig", rng: random.Random) -> Dict[str, Any]:
    """Generate a compact, combat-ready 5e-ish stat block for an NPC.

    Intentionally simplified: enough for play, not full PC rules.
    """
    role = str(npc.get("role") or "")
    cls = _pick_class_for_role(rng, role)
    tmpl = CLASS_TEMPLATES.get(cls, CLASS_TEMPLATES["Fighter"])
    power = (getattr(cfg, "power", None) or "Standard")
    level = _power_to_level(power, rng)
    pb = proficiency_bonus(level)

    stats = npc.get("stats") or {}
    str_mod = _mod(int(stats.get("STR", 10)))
    dex_mod = _mod(int(stats.get("DEX", 10)))
    con_mod = _mod(int(stats.get("CON", 10)))
    int_mod = _mod(int(stats.get("INT", 10)))
    wis_mod = _mod(int(stats.get("WIS", 10)))
    cha_mod = _mod(int(stats.get("CHA", 10)))

    # Armor / AC
    armor_cat = tmpl.get("armor", "none")
    armor_name, base = rng.choice(ARMOR_CHOICES.get(armor_cat, ARMOR_CHOICES["none"]))
    shield = bool(tmpl.get("shield")) and rng.random() < (0.65 if power in ("Veteran", "Elite") else 0.4)
    shield_bonus = 2 if shield else 0
    if armor_cat == "none":
        ac = 10 + dex_mod + shield_bonus
    elif armor_cat == "light":
        ac = base + dex_mod + shield_bonus
    elif armor_cat == "medium":
        ac = base + min(2, dex_mod) + shield_bonus
    else:  # heavy
        ac = base + shield_bonus

    # HP
    hd = int(tmpl.get("hit_die", 8))
    # average HP per level = (hd//2 + 1) (5e average)
    avg = (hd // 2) + 1
    hp = max(level, (avg * level) + (con_mod * level))
    # small variability
    hp = int(max(level, hp + rng.randint(-level, level)))

    speed = 30
    if role.lower() in ("hunter", "scout"):
        speed = 35

    # Skills (lightweight)
    skills = []
    if cls in ("Rogue",):
        skills = ["Stealth", "Sleight of Hand", "Perception"]
    elif cls in ("Ranger",):
        skills = ["Perception", "Survival", "Stealth"]
    elif cls in ("Cleric", "Paladin"):
        skills = ["Insight", "Religion"]
    elif cls in ("Wizard",):
        skills = ["Arcana", "Investigation"]
    elif cls in ("Bard",):
        skills = ["Performance", "Persuasion"]
    else:
        skills = ["Athletics", "Intimidation"] if role in ("Guard", "Officer", "Mercenary") else ["Perception"]

    # Saving throws
    save_profs = set(tmpl.get("save_profs", ()))
    save_mods = {"STR": str_mod, "DEX": dex_mod, "CON": con_mod, "INT": int_mod, "WIS": wis_mod, "CHA": cha_mod}
    saves = {}
    for abil, m in save_mods.items():
        saves[abil] = m + (pb if abil in save_profs else 0)

    # Attacks
    attacks = []
    is_melee = True
    if cls in ("Ranger", "Wizard", "Warlock") and rng.random() < 0.65:
        is_melee = False
    if cls in ("Rogue", "Bard") and rng.random() < 0.55:
        is_melee = False

    if is_melee:
        pool = WEAPONS["melee_martial"] if "martial" in str(tmpl.get("weapons", "")) else WEAPONS["melee_simple"]
        wname, dmg = rng.choice(pool)
        attack_mod = max(str_mod, dex_mod) if cls in ("Rogue",) else str_mod
        to_hit = attack_mod + pb
        attacks.append({
            "name": wname,
            "type": "Melee Weapon Attack",
            "to_hit": to_hit,
            "reach": "5 ft.",
            "damage": f"{dmg} + {attack_mod}",
            "damage_type": "slashing" if "sword" in wname.lower() or "glaive" in wname.lower() else "bludgeoning",
        })
    else:
        pool = WEAPONS["ranged_martial"] if "martial" in str(tmpl.get("weapons", "")) else WEAPONS["ranged_simple"]
        wname, dmg = rng.choice(pool)
        attack_mod = dex_mod
        to_hit = attack_mod + pb
        attacks.append({
            "name": wname,
            "type": "Ranged Weapon Attack",
            "to_hit": to_hit,
            "range": "80/320 ft." if "bow" in wname.lower() else "30/120 ft.",
            "damage": f"{dmg} + {attack_mod}",
            "damage_type": "piercing",
        })

    # Optional spellcasting
    tradition = tmpl.get("caster")
    spells: Dict[str, Any] = {}
    if tradition:
        can, s1, s2, s3 = _spell_lists_for(tradition)
        # Determine max spell level by level
        max_sl = 1
        if level >= 5:
            max_sl = 3
        elif level >= 3:
            max_sl = 2
        # pick spells
        spells["tradition"] = tradition
        spells["spell_attack_bonus"] = (pb + (int_mod if tradition == "arcane" else wis_mod if tradition in ("divine","primal") else cha_mod))
        key_mod = int_mod if tradition == "arcane" else wis_mod if tradition in ("divine","primal") else cha_mod
        spells["save_dc"] = 8 + pb + key_mod
        spells["cantrips"] = rng.sample(can, k=min(2, len(can)))
        if max_sl >= 1:
            spells["1st"] = rng.sample(s1, k=min(3, len(s1)))
        if max_sl >= 2:
            spells["2nd"] = rng.sample(s2, k=min(2, len(s2)))
        if max_sl >= 3:
            spells["3rd"] = rng.sample(s3, k=min(2, len(s3)))

        # If we generated a caster, also add a simple "spell" attack option
        sp_name = "Arcane Bolt" if tradition == "arcane" else "Radiant Spark" if tradition == "divine" else "Thorn Whip"
        sp_to_hit = spells["spell_attack_bonus"]
        dmg_die = "1d10" if level >= 5 else "1d8"
        attacks.append({
            "name": sp_name,
            "type": "Spell Attack",
            "to_hit": sp_to_hit,
            "range": "120 ft.",
            "damage": f"{dmg_die} + {key_mod}",
            "damage_type": "force" if tradition == "arcane" else "radiant" if tradition == "divine" else "piercing",
        })

    # Equipment list (kept short)
    equipment = [armor_name]
    if shield:
        equipment.append("Shield")
    equipment.append(attacks[0]["name"])
    if len(attacks) > 1:
        equipment.append(attacks[1]["name"])
    # Add a couple flavorful items
    equipment.extend(rng.sample([
        "Dagger", "Lantern", "Rope (50 ft.)", "Pouch of coins", "Sealing wax", "Holy token",
        "Field rations", "Lockpicks", "Map scraps", "Vial of salt", "Scribbled letters"
    ], k=2))

    # Simple traits
    traits = []
    if cls == "Rogue":
        traits.append("**Cunning Action:** Can Dash, Disengage, or Hide as a bonus action.")
    if cls in ("Fighter", "Paladin") and power in ("Veteran", "Elite"):
        traits.append("**Second Wind:** Once per combat, regains a small burst of HP (as an action).")
    if tradition:
        traits.append("**Spellcasting:** Uses the listed spell DC/bonus; spells are chosen for quick play, not strict preparation rules.")

    return {
        "class": cls,
        "level": level,
        "power": power,
        "proficiency_bonus": pb,
        "ac": int(ac),
        "hp": int(hp),
        "speed": speed,
        "saves": saves,
        "skills": skills,
        "attacks": attacks,
        "equipment": equipment,
        "spells": spells,
        "traits": traits,
    }

def combat_block_md(combat: Dict[str, Any], stats: Dict[str, int]) -> str:
    if not combat:
        return ""
    cls = combat.get("class", "")
    level = combat.get("level", "")
    pb = combat.get("proficiency_bonus", "")
    ac = combat.get("ac", "")
    hp = combat.get("hp", "")
    speed = combat.get("speed", 30)

    lines = []
    lines.append(f"**Combat:** {cls} (Lvl {level})  |  **AC** {ac}  |  **HP** {hp}  |  **Speed** {speed} ft.  |  **PB** +{pb}")
    saves = combat.get("saves") or {}
    if saves:
        save_bits = []
        for abil in ABILITIES:
            v = saves.get(abil)
            if v is None:
                continue
            sign = "+" if int(v) >= 0 else ""
            save_bits.append(f"{abil} {sign}{int(v)}")
        if save_bits:
            lines.append("**Saves:** " + ", ".join(save_bits))
    skills = combat.get("skills") or []
    if skills:
        lines.append("**Skills:** " + ", ".join(map(str, skills)))

    traits = combat.get("traits") or []
    if traits:
        lines.append("**Traits:** " + "  ".join(map(str, traits)))

    attacks = combat.get("attacks") or []
    if attacks:
        lines.append("")
        lines.append("**Attacks:**")
        for a in attacks:
            nm = a.get("name","Attack")
            typ = a.get("type","")
            to_hit = int(a.get("to_hit",0))
            sign = "+" if to_hit >= 0 else ""
            reach = a.get("reach") or ""
            rng = a.get("range") or ""
            rr = reach if reach else rng
            dmg = a.get("damage","")
            dt = a.get("damage_type","")
            tail = f" ({rr})" if rr else ""
            lines.append(f"- *{nm}* — {typ}: {sign}{to_hit} to hit{tail}; Hit: {dmg} {dt}".rstrip())

    spells = combat.get("spells") or {}
    if spells:
        lines.append("")
        lines.append(f"**Spellcasting ({spells.get('tradition','').title()}):** DC {spells.get('save_dc','?')} | Spell Attack +{spells.get('spell_attack_bonus','?')}")
        if spells.get("cantrips"):
            lines.append("- Cantrips: " + ", ".join(spells["cantrips"]))
        for k in ("1st","2nd","3rd"):
            if spells.get(k):
                lines.append(f"- {k} level: " + ", ".join(spells[k]))

    eq = combat.get("equipment") or []
    if eq:
        lines.append("")
        lines.append("**Equipment:** " + ", ".join(map(str, eq)))

    return "\n".join(lines).rstrip()

# ---------------------------
# Config
# ---------------------------

@dataclass
class NpcGenConfig:
    culture: str = "Common"
    role: str = "Any"
    faction: str = ""
    count: int = 8

    # Combat generation
    power: str = "Standard"  # Common, Standard, Veteran, Elite

    # Relationship web tuning
    relationship_density: float = 0.35  # 0..1
    max_relationships_per_npc: int = 3


# ---------------------------
# Culture packs (small built-ins; easy to extend later)
# ---------------------------

CULTURE_PACKS: Dict[str, Dict[str, Sequence[str]]] = {
    "Common": {
        "first": (
            "Alden","Bran","Celia","Dara","Edric","Faye","Garin","Helena","Ivo","Jora",
            "Kellan","Lysa","Marek","Nera","Orin","Perrin","Quinn","Rhea","Silas","Tamsin",
            "Ulric","Vera","Wren","Ysolde","Zane"
        ),
        "last": (
            "Ashford","Briar","Crowe","Dunlow","Evers","Fenwick","Gray","Hallow","Ironwood","Jasper",
            "Kettle","Lark","Moss","Nightingale","Oakens","Pryce","Quill","Rook","Thorne","Vellum"
        ),
        "appearance": (
            "scarred","immaculate","mud-stained","ink-stained","laugh-lines","missing tooth","restless eyes",
            "calloused hands","perfumed","sunburnt","tattooed","ringed fingers","limp","soft voice","hard stare",
            "hooded","brass earrings","threadbare","fine boots","gloves","smoke-scented"
        ),
    },
    "High Elven": {
        "first": (
            "Aelith","Caerwyn","Elyra","Faelar","Ithil","Lethariel","Maelis","Nym","Saelion","Thalindra",
            "Vaelis","Yvanna"
        ),
        "last": (
            "Moonwhisper","Silverbough","Starweave","Glimmerleaf","Dawnspire","Nightbloom","Sunsong"
        ),
        "appearance": (
            "luminous eyes","immaculate robes","silver hair","braided hair","perfumed","moon-pale skin",
            "delicate hands","soft laugh","cold smile","ancient jewelry","star-chart tattoos"
        ),
    },
    "Dwarven": {
        "first": (
            "Brom","Dagna","Eirik","Gund","Hilda","Korin","Marga","Orla","Rurik","Sigrid","Thrain","Vigdis"
        ),
        "last": (
            "Stonebeard","Ironhammer","Deepdelver","Goldvein","Coalbraid","Anvilhand","Boulderborn"
        ),
        "appearance": (
            "soot-streaked","braided beard","braided hair","missing fingertip","runescar","thick gloves","coal-smell",
            "iron tattoos","splinted knuckles","heavy boots","laughs too loud"
        ),
    },
    "Gutterfolk": {
        "first": (
            "Brin","Cass","Dred","Etta","Fizz","Gad","Huck","Jinx","Kip","Lark","Midge","Nox","Pip","Rook","Skit"
        ),
        "last": (
            "No-Name","Stitch","Backalley","Tallow","Rats","Hinge","Coppers","Soot","Shiv"
        ),
        "appearance": (
            "streetwise grin","knife-scar","inked knuckles","patched coat","filthy boots","quick hands","shifty eyes",
            "cheap perfume","wet hair","ink-stained","coin-biter","bandaged wrist"
        ),
    },
}


# ---------------------------
# Roles
# ---------------------------

ROLES: Sequence[str] = (
    "Merchant",
    "Cultist",
    "Officer",
    "Guard",
    "Fence",
    "Innkeeper",
    "Priest",
    "Scribe",
    "Smuggler",
    "Healer",
    "Scout",
    "Apothecary",
)

ROLE_TICS: Dict[str, Sequence[str]] = {
    "Merchant": ("measures everything", "knows the price of fear", "always has a ledger", "talks in margins"),
    "Cultist": ("smiles at the wrong moments", "avoids mirrors", "whispers names like prayers", "keeps odd hours"),
    "Officer": ("polishes insignia", "speaks in procedure", "never sits with their back to a door", "collects favors"),
    "Guard": ("counts exits", "fiddles with keys", "hates paperwork", "deflects with jokes"),
    "Fence": ("never uses real names", "tests weight of coins", "has too many locks", "owes somebody"),
    "Innkeeper": ("remembers everyone", "hears everything", "knows which beds creak", "sweeps while listening"),
    "Priest": ("uses blessing as threat", "keeps a hidden vice", "carries many small charms", "smells of incense"),
    "Scribe": ("corrects your grammar", "writes in tiny script", "collects rumors", "is terrified of fire"),
    "Smuggler": ("speaks in routes", "knows secret doors", "hates bright light", "keeps a spare identity"),
    "Healer": ("counts pulses", "lies gently", "knows poisons", "won't touch cold iron"),
    "Scout": ("always watching rooftops", "keeps maps in boots", "walks silently", "never stops moving"),
    "Apothecary": ("stains of herbs", "smells like bitter tea", "collects rare jars", "barters in cures"),
}


# ---------------------------
# Secrets & rumors (templates)
# ---------------------------

SECRETS: Sequence[str] = (
    "is working for {faction} under a false name",
    "has a key that doesn't match Any lock in town",
    "owes a life-debt to someone they won't name",
    "is the last survivor of a failed expedition",
    "has been forging permits and seals",
    "is quietly hunting a shapeshifter",
    "keeps a forbidden book wrapped in oilcloth",
    "saw a noble commit a crime and is terrified",
)

RUMORS: Sequence[str] = (
    "says the old well is deeper than the map claims",
    "heard chanting beneath the cobbles after midnight",
    "claims a caravan vanished between two milestones",
    "insists the mayor has never eaten on public record",
    "swears the graveyard lights move when nobody looks",
    "says the river sometimes flows uphill at dawn",
    "heard a name spoken by the bell with no ringer",
    "claims the inn's attic door appears on different walls",
)


# ---------------------------
# Relationship web
# ---------------------------

REL_TYPES: Sequence[Tuple[str, str]] = (
    ("ally", "is an ally of"),
    ("rival", "is a rival of"),
    ("owes", "owes money to"),
    ("blackmail", "is blackmailing"),
    ("family", "is family with"),
    ("handler", "is the handler of"),
    ("informant", "feeds info to"),
    ("lover", "is secretly involved with"),
    ("protects", "quietly protects"),
    ("hates", "would gladly ruin"),
)


# ---------------------------
# Generation helpers
# ---------------------------

def list_cultures() -> List[str]:
    return sorted(CULTURE_PACKS.keys())


def list_roles() -> List[str]:
    return ["Any", *list(ROLES)]


def _pick_name(rng: random.Random, culture: str) -> str:
    pack = CULTURE_PACKS.get(culture) or CULTURE_PACKS["Common"]
    first = rng.choice(list(pack["first"]))
    last = rng.choice(list(pack["last"]))

    # Small chance of epithet / street-name
    if rng.random() < 0.12:
        epithet = rng.choice(["of the Bridge", "the Quiet", "Red-Hand", "Two-Coins", "Blackthread", "Pale-Eye"])
        return f"{first} {last} {epithet}"

    return f"{first} {last}"


def _pick_appearance_tags(rng: random.Random, culture: str, k_min: int = 2, k_max: int = 4) -> List[str]:
    pack = CULTURE_PACKS.get(culture) or CULTURE_PACKS["Common"]
    pool = list(pack.get("appearance", ()))
    k = rng.randint(k_min, k_max)
    rng.shuffle(pool)
    return pool[: min(k, len(pool))]


def _pick_role(rng: random.Random, role: str) -> str:
    if role and role != "Any":
        return role
    return rng.choice(list(ROLES))


def _format_secret(rng: random.Random, faction: str) -> str:
    tmpl = rng.choice(list(SECRETS))
    f = faction.strip() or rng.choice(["the City Watch", "the Candle Cult", "House Vellum", "the Smugglers' Ring"])
    return tmpl.format(faction=f)


def _format_rumor(rng: random.Random) -> str:
    return rng.choice(list(RUMORS))


def generate_roster(cfg: NpcGenConfig, rng: random.Random) -> Dict[str, object]:
    """Generate a roster plus a relationship web.

    Returns a JSON-serializable dict.
    """

    count = max(1, int(cfg.count))
    culture = cfg.culture or "Common"
    faction = (cfg.faction or "").strip()

    npcs: List[Dict[str, object]] = []
    for i in range(count):
        name = _pick_name(rng, culture)
        role = _pick_role(rng, cfg.role)
        tics = list(ROLE_TICS.get(role, ()))
        tic = rng.choice(tics) if tics else ""

        npc = {
            "id": f"npc{i+1}",
            "name": name,
            "culture": culture,
            "role": role,
            "faction": faction,
            "appearance": _pick_appearance_tags(rng, culture),
            "tic": tic,
            "secret": _format_secret(rng, faction),
            "rumors": [ _format_rumor(rng) for _ in range(rng.randint(1, 2)) ],
            "stats": roll_ability_scores(rng),
            "combat": {},
            "notes": "",
        }
        npc["combat"] = generate_combat_profile(npc, cfg, rng)
        npcs.append(npc)

    rels = generate_relationships(
        npc_ids=[n["id"] for n in npcs],
        rng=rng,
        density=float(cfg.relationship_density),
        max_per_npc=int(cfg.max_relationships_per_npc),
    )

    return {
        "version": 1,
        "culture": culture,
        "faction": faction,
        "npcs": npcs,
        "relationships": rels,
    }


def generate_relationships(
    npc_ids: Sequence[str],
    rng: random.Random,
    density: float = 0.35,
    max_per_npc: int = 3,
) -> List[Dict[str, str]]:
    """Generate a loose relationship web as edge list.

    Output is JSON-serializable.
    """

    ids = list(npc_ids)
    n = len(ids)
    if n < 2:
        return []

    density = max(0.0, min(1.0, float(density)))
    max_per_npc = max(0, int(max_per_npc))

    # Determine target edges ~ density * complete graph
    complete = n * (n - 1) // 2
    target_edges = int(round(density * complete))

    # Cap by per-node limit
    # upper bound edges ~ (n*max_per_npc)/2
    if max_per_npc > 0:
        target_edges = min(target_edges, (n * max_per_npc) // 2)

    # Build candidate pairs
    pairs: List[Tuple[str, str]] = []
    for i in range(n):
        for j in range(i + 1, n):
            pairs.append((ids[i], ids[j]))
    rng.shuffle(pairs)

    degree: Dict[str, int] = {i: 0 for i in ids}
    edges: List[Dict[str, str]] = []

    for a, b in pairs:
        if len(edges) >= target_edges:
            break
        if max_per_npc > 0 and (degree[a] >= max_per_npc or degree[b] >= max_per_npc):
            continue

        rel_key, rel_text = rng.choice(list(REL_TYPES))

        # Randomly orient some relations to feel more personal
        if rel_key in {"owes", "blackmail", "handler", "informant", "protects"} and rng.random() < 0.5:
            a, b = b, a

        edges.append({
            "a": a,
            "b": b,
            "type": rel_key,
            "text": rel_text,
        })
        degree[a] += 1
        degree[b] += 1

    return edges

# ---------------------------
# Formatting helpers (Markdown)
# ---------------------------



def npc_to_markdown(
    npc: Dict[str, Any],
    *,
    roster: Optional[Dict[str, Any]] = None,
    faction: str = "",
    include_header: bool = True
) -> str:
    """Render a single NPC to a session-useful Markdown blurb.

    Accepts optional roster (with relationships) to include a per-NPC relationship section.
    """
    name = npc.get("name", "Unknown")
    role = npc.get("role", "")
    culture = npc.get("culture", "")
    npc_faction = (npc.get("faction") or "").strip()
    if not faction:
        faction = npc_faction

    appearance = list(npc.get("appearance") or [])
    rumors = list(npc.get("rumors") or npc.get("hooks") or [])
    # legacy/compat: a single "secret" string or "secrets" list
    secret_one = (npc.get("secret") or "").strip()
    secrets_list = list(npc.get("secrets") or [])
    secrets: List[str] = []
    if secret_one:
        secrets.append(secret_one)
    for s in secrets_list:
        if s and str(s).strip():
            secrets.append(str(s).strip())

    stats = npc.get("stats") or {}

    lines: List[str] = []
    if include_header:
        lines.append(f"## {name}")

    meta_bits: List[str] = []
    if role:
        meta_bits.append(str(role))
    if culture:
        meta_bits.append(str(culture))
    if faction:
        meta_bits.append(f"Faction: {faction}")

    if meta_bits:
        lines.append("_" + " • ".join(meta_bits) + "_")

    if stats:
        lines.append("")
        lines.append("**Stats (5e):** " + ability_block_md(stats))

    combat = npc.get("combat") or {}
    if combat:
        lines.append("")
        lines.append(combat_block_md(combat, stats))

    tic = (npc.get("tic") or "").strip()
    if tic:
        lines.append("")
        lines.append(f"**Tic:** {tic}")

    if appearance:
        lines.append("")
        lines.append("**Appearance:** " + ", ".join([str(a) for a in appearance[:6]]))

    if rumors:
        lines.append("")
        lines.append("**Hooks / Rumors:**")
        for h in rumors[:6]:
            lines.append(f"- {h}")

    if secrets:
        lines.append("")
        lines.append("**Secrets:**")
        for s in secrets[:3]:
            lines.append(f"- {s}")

    # Per-NPC relationships (if roster provided)
    if roster and roster.get("relationships"):
        rels = roster.get("relationships") or []
        npcs = roster.get("npcs") or []
        by_id = {n.get("id"): n for n in npcs if n.get("id")}
        my_id = npc.get("id")
        my_rels = [e for e in rels if e.get("a") == my_id or e.get("b") == my_id]
        if my_rels:
            lines.append("")
            lines.append("**Relationships:**")
            for e in my_rels[:6]:
                other_id = e.get("b") if e.get("a") == my_id else e.get("a")
                other = by_id.get(other_id, {})
                other_name = other.get("name", "?")
                text = e.get("text", e.get("type", ""))
                lines.append(f"- {other_name} — {text}")

    notes = (npc.get("notes") or "").strip()
    if notes:
        lines.append("")
        lines.append("**Notes:** " + notes)

    return "\n".join(lines).strip() + "\n"


def npc_roster_to_markdown(roster: Dict[str, Any], *, title: str = "NPC Roster") -> str:
    """Render a roster + relationship web to Markdown."""
    roster = roster or {}
    npcs = roster.get("npcs") or []
    rels = roster.get("relationships") or []
    faction = roster.get("faction") or ""
    culture = roster.get("culture") or ""

    # Build quick lookup
    by_id: Dict[str, Dict[str, Any]] = {n.get("id"): n for n in npcs if n.get("id")}

    lines: List[str] = []
    lines.append(f"# {title}")
    sub = []
    if culture:
        sub.append(f"Culture: {culture}")
    if faction:
        sub.append(f"Faction: {faction}")
    if sub:
        lines.append("_" + " • ".join(sub) + "_")

    lines.append("")
    lines.append("## Roster")
    for n in npcs:
        nm = n.get("name", "Unknown")
        rl = n.get("role", "")
        tag = f" — {rl}" if rl else ""
        lines.append(f"- **{nm}**{tag}")

    lines.append("")
    lines.append("---")
    lines.append("")

    for n in npcs:
        lines.append(npc_to_markdown(n, faction=faction, include_header=True).rstrip())
        lines.append("")

    if rels:
        lines.append("---")
        lines.append("")
        lines.append("## Relationship Web")
        for e in rels:
            a = by_id.get(e.get("a"), {})
            b = by_id.get(e.get("b"), {})
            a_name = a.get("name", "?")
            b_name = b.get("name", "?")
            text = e.get("text", e.get("type", ""))
            lines.append(f"- **{a_name}** ↔ **{b_name}** — {text}")

    return "\n".join(lines).rstrip() + "\n"
