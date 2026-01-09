from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import json
import math
import random
import time


# -----------------------------
# Data models
# -----------------------------

@dataclass
class EncounterInputs:
    party_level: int = 3
    party_size: int = 4
    party_condition: str = "Fresh"  # Fresh/Wounded/Exhausted/Desperate
    biome: str = "Dungeon"
    dungeon_tag: str = ""
    faction: str = ""
    faction_profile: str = "Auto"  # Auto or an archetype id
    encounter_type: str = "Auto"   # Auto or encounter type id
    difficulty: str = "Medium"     # Easy/Medium/Hard/Deadly
    narrative_role: str = "Neutral"  # Foreshadowing/Attrition/Climax/Complication/Neutral
    lethality: int = 50            # 0..100 (affects morale & composition)
    allow_social: bool = True
    allow_hazard: bool = True
    chain_mode: bool = False
    chain_steps: int = 2  # 2..3
    lock_seed: bool = False
    seed: int = 0                  # only used if lock_seed True
    notes: str = ""                # freeform GM intent

@dataclass
class MonsterPick:
    name: str
    kind: str
    role: str
    cr: float
    count: int = 1
    tags: List[str] = None

@dataclass
class GeneratedStatBlock:
    name: str
    size: str
    kind: str
    alignment: str
    armor_class: int
    hit_points: int
    speed: str
    str_: int
    dex: int
    con: int
    int_: int
    wis: int
    cha: int
    proficiency_bonus: int
    attack_bonus: int
    save_dc: int
    damage_per_round: int
    traits: List[str]
    actions: List[str]

@dataclass
class EncounterResult:
    title: str
    seed_used: int
    created_ts: float
    inputs: Dict[str, Any]
    opposition: List[Dict[str, Any]]
    statblocks: List[Dict[str, Any]]
    markdown: str
    tags: List[str]


# -----------------------------
# Table loading
# -----------------------------

def _load_json_table(tables_dir: Path, name: str) -> Any:
    p = tables_dir / name
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)

def load_tables(tables_dir: Path) -> Dict[str, Any]:
    return {
        "biomes": _load_json_table(tables_dir, "biomes.json"),
        "encounter_types": _load_json_table(tables_dir, "encounter_types.json"),
        "factions": _load_json_table(tables_dir, "factions.json"),
        "monsters": _load_json_table(tables_dir, "monsters.json"),
    }


# -----------------------------
# Heuristics (5e-ish, but not DMG tables)
# -----------------------------

_CR_POINTS = {
    0.0: 1,
    0.125: 2,
    0.25: 4,
    0.5: 8,
    1.0: 16,
    2.0: 24,
    3.0: 32,
    4.0: 40,
    5.0: 48,
    6.0: 56,
    7.0: 64,
    8.0: 72,
    9.0: 80,
    10.0: 88,
    11.0: 96,
    12.0: 104,
    13.0: 112,
    14.0: 120,
    15.0: 128,
    16.0: 136,
    17.0: 144,
    18.0: 152,
    19.0: 160,
    20.0: 168,
}

def cr_to_points(cr: float) -> int:
    # Snap to nearest known key
    keys = sorted(_CR_POINTS.keys())
    closest = min(keys, key=lambda k: abs(k - float(cr)))
    return int(_CR_POINTS.get(closest, 16))

def threat_budget(party_level: int, party_size: int, difficulty: str, condition: str, lethality: int) -> int:
    # A simple, tunable "threat points" budget (not DMG XP).
    base = max(1, party_level) * max(1, party_size) * 12

    diff_mult = {
        "Easy": 0.75,
        "Medium": 1.00,
        "Hard": 1.25,
        "Deadly": 1.60,
    }.get(difficulty, 1.0)

    cond_mult = {
        "Fresh": 1.00,
        "Wounded": 0.90,
        "Exhausted": 0.80,
        "Desperate": 0.70,
    }.get(condition, 1.0)

    # Lethality nudges up/down a bit (0..100)
    leth_mult = 0.85 + (max(0, min(100, int(lethality))) / 100.0) * 0.35  # 0.85..1.20

    return int(base * diff_mult * cond_mult * leth_mult)


def honesty_meter(budget: int, party_level: int, party_size: int) -> str:
    baseline = max(1, party_level) * max(1, party_size) * 12
    ratio = budget / float(baseline)
    if ratio < 0.85:
        return "Low-pressure (mostly safe unless mishandled)."
    if ratio < 1.10:
        return "Fair fight (resource cost likely)."
    if ratio < 1.35:
        return "Swingy (bad positioning can turn it deadly)."
    return "High-danger (deadly head-on; requires smart play or avoidance)."

def proficiency_from_cr(cr: float) -> int:
    # Roughly PB 2..6 across CR 0..20
    return max(2, min(6, 2 + int(max(0.0, cr) // 4)))

def base_stats_from_cr(rng: random.Random, cr: float) -> Tuple[int,int,int,int,int,int]:
    # Produce plausible stat arrays, biased by "monster-y" CR
    crf = max(0.0, float(cr))
    # baseline 10..18
    base = 10 + int(min(8, crf / 2.5))
    spread = 6 + int(min(6, crf / 3.0))
    stats = [base + rng.randint(-2, 2) for _ in range(6)]
    # give two strong stats
    for i in rng.sample(range(6), k=2):
        stats[i] += rng.randint(2, spread)
    # clamp
    stats = [max(6, min(24, s)) for s in stats]
    return stats[0], stats[1], stats[2], stats[3], stats[4], stats[5]

def derived_combat_numbers(rng: random.Random, cr: float) -> Tuple[int,int,int,int,int]:
    pb = proficiency_from_cr(cr)
    ac = 12 + int(cr // 3) + rng.randint(0, 2)  # 12..~20
    hp = int((14 + cr * 14) * rng.uniform(0.85, 1.15))
    atk = pb + int(cr / 2) + rng.randint(0, 1)
    dc = 8 + pb + int(cr / 2)
    dpr = int((4 + cr * 6) * rng.uniform(0.85, 1.15))
    return ac, hp, atk, dc, dpr


# -----------------------------
# Encounter generation
# -----------------------------

def _weighted_choice(rng: random.Random, items: List[Tuple[Any, float]]) -> Any:
    total = sum(max(0.0, w) for _, w in items)
    if total <= 0:
        return rng.choice([it for it, _ in items])
    r = rng.random() * total
    acc = 0.0
    for it, w in items:
        acc += max(0.0, w)
        if r <= acc:
            return it
    return items[-1][0]

def _pick_biome_complications(rng: random.Random, biome_data: Dict[str, Any], count: int = 2) -> List[str]:
    comps = list(biome_data.get("complications") or [])
    rng.shuffle(comps)
    return comps[:max(1, count)] if comps else ["Unclear footing", "Low visibility"]

def _pick_encounter_type(rng: random.Random, tables: Dict[str, Any], biome: str, forced_id: str) -> Dict[str, Any]:
    ets = tables["encounter_types"]
    if forced_id and forced_id != "Auto":
        for e in ets:
            if e.get("id") == forced_id:
                return e
    # weighted by biome
    weights = []
    for e in ets:
        w = (e.get("weights") or {}).get(biome, 1)
        weights.append((e, float(w)))
    return _weighted_choice(rng, weights)

def _pick_faction_profile(rng: random.Random, tables: Dict[str, Any], forced_id: str) -> Dict[str, Any]:
    facs = tables["factions"]
    if forced_id and forced_id != "Auto":
        for f in facs:
            if f.get("id") == forced_id:
                return f
    return rng.choice(facs) if facs else {"id":"generic","name":"Unknown","traits":["wary"],"morale_base":8,"tactics":["hold ground"],"parley":["talk"]}

def _candidate_monsters(tables: Dict[str, Any], biome: str, faction_profile: Dict[str, Any]) -> List[Dict[str, Any]]:
    monsters = tables["monsters"] or []
    fac_id = (faction_profile.get("id") or "").lower()
    candidates = []
    for m in monsters:
        tags = [t.lower() for t in (m.get("tags") or [])]
        score = 0
        if biome.lower() in tags:
            score += 3
        if fac_id and fac_id in tags:
            score += 3
        # slight bonus for universal tags
        if "dungeon" in tags and biome == "Dungeon":
            score += 1
        if score > 0:
            candidates.append((m, score))
    if candidates:
        # return sorted by score desc
        candidates.sort(key=lambda x: x[1], reverse=True)
        return [m for m,_ in candidates]
    return list(monsters)

def _pick_role_mix(rng: random.Random, encounter_type_id: str, allow_social: bool, allow_hazard: bool) -> List[str]:
    # Defines desired roles order
    if encounter_type_id == "social" and allow_social:
        return ["leader", "frontliner", "skirmisher"]
    if encounter_type_id == "ritual":
        return ["leader", "caster", "controller", "frontliner"]
    if encounter_type_id in ("ambush", "chase"):
        return ["skirmisher", "ranged", "controller"]
    if encounter_type_id == "hazard" and allow_hazard:
        return ["controller", "frontliner", "minion"]
    # default
    return ["frontliner", "skirmisher", "ranged", "leader"]

def _snap_cr_to_party(crs: List[float], party_level: int, rng: random.Random) -> float:
    # bias CR near party_level/2 .. party_level+1 based on available list
    if not crs:
        return 1.0
    target = max(0.125, party_level * rng.uniform(0.35, 0.9))
    return min(crs, key=lambda c: abs(float(c) - target))

def _pick_monsters_for_budget(
    rng: random.Random,
    candidates: List[Dict[str, Any]],
    party_level: int,
    budget: int,
    desired_roles: List[str],
) -> List[MonsterPick]:
    picks: List[MonsterPick] = []
    remaining = budget

    def find_candidate(role: str) -> Optional[Dict[str, Any]]:
        role_l = role.lower()
        role_aliases = {
            "caster": ["caster", "support"],
            "ranged": ["ranged", "skirmisher"],
            "leader": ["leader"],
            "controller": ["controller"],
            "frontliner": ["frontliner"],
            "minion": ["minion"],
            "skirmisher": ["skirmisher", "ranged"],
            "support": ["support", "caster"],
        }.get(role_l, [role_l])

        pool = []
        for m in candidates:
            roles = [r.lower() for r in (m.get("roles") or [])]
            if any(a in roles for a in role_aliases):
                pool.append(m)
        return rng.choice(pool) if pool else (rng.choice(candidates) if candidates else None)

    # Ensure at least 2 groups when possible
    groups_target = 2 if budget >= 40 else 1
    for role in desired_roles:
        if remaining <= 0:
            break
        m = find_candidate(role)
        if not m:
            break
        cr = _snap_cr_to_party(m.get("cr") or [], party_level, rng)
        pts = cr_to_points(cr)
        if pts > remaining and picks:
            continue
        count = 1
        # minion packs
        if "minion" in [r.lower() for r in (m.get("roles") or [])] and remaining >= pts * 3:
            count = rng.randint(2, 5)
        # skirmisher pairs sometimes
        if role.lower() in ("skirmisher", "ranged") and remaining >= pts * 2 and rng.random() < 0.4:
            count = 2
        total_pts = pts * count
        if total_pts > remaining and count > 1:
            count = max(1, remaining // pts)
            total_pts = pts * count
        if total_pts <= 0:
            continue
        picks.append(MonsterPick(
            name=str(m.get("name") or "Unknown"),
            kind=str(m.get("kind") or "Creature"),
            role=role,
            cr=float(cr),
            count=int(max(1, count)),
            tags=list(m.get("tags") or []),
        ))
        remaining -= total_pts
        if len(picks) >= groups_target and remaining < budget * 0.25:
            break

    # If budget remains, sprinkle minions
    if remaining > budget * 0.25 and candidates:
        for _ in range(2):
            m = find_candidate("minion") or rng.choice(candidates)
            cr = min(m.get("cr") or [0.25])
            pts = cr_to_points(cr)
            if pts <= 0:
                continue
            count = min(6, max(2, remaining // pts))
            if count >= 2:
                picks.append(MonsterPick(
                    name=str(m.get("name") or "Minions"),
                    kind=str(m.get("kind") or "Creature"),
                    role="minion",
                    cr=float(cr),
                    count=int(count),
                    tags=list(m.get("tags") or []),
                ))
                remaining -= pts * count
            if remaining <= budget * 0.15:
                break

    return picks

def _make_statblock(rng: random.Random, base_name: str, kind: str, cr: float, role: str, faction_name: str) -> GeneratedStatBlock:
    size = rng.choice(["Medium", "Medium", "Small", "Large"])
    alignment = rng.choice(["unaligned", "neutral", "lawful neutral", "chaotic neutral", "neutral evil"])
    ac, hp, atk, dc, dpr = derived_combat_numbers(rng, cr)
    s, d, c, i, w, ch = base_stats_from_cr(rng, cr)

    # role tweaks
    role_l = (role or "").lower()
    traits = []
    actions = []

    if "leader" in role_l:
        traits.append("**Commanding Presence.** Allies within 30 ft gain +1 to attack rolls while this creature is conscious.")
        hp = int(hp * 1.15)
    if "controller" in role_l or "caster" in role_l or "support" in role_l:
        dc += 1
        traits.append("**Battle Control.** Once per round, it can impose disadvantage on one creature's next attack if within 60 ft (describe as a trick, spell, or shout).")
    if "skirmisher" in role_l or "ranged" in role_l:
        traits.append("**Skirmisher.** The creature can take the Disengage action as a bonus action 1/round.")
        dpr = int(dpr * 0.95)
    if "minion" in role_l:
        hp = max(4, int(hp * 0.35))
        traits.append("**Minion.** If this creature takes damage from an area effect, it succeeds on the save but still takes half damage on a success.")

    # Actions
    actions.append(f"**Multiattack (if CR≥2).** If CR is 2 or higher, it makes 2 attacks.")
    actions.append(f"**Weapon Attack.** Melee or Ranged Weapon Attack: +{atk} to hit, reach 5 ft or range 80/320 ft, one target. Hit: {max(1, int(dpr*0.65))} damage.")
    if dc >= 12 and ("controller" in role_l or "caster" in role_l):
        actions.append(f"**Control Effect (Recharge 5–6).** One creature within 60 ft must succeed on a DC {dc} save or be *hindered* until end of its next turn (speed halved; can't take reactions).")

    name = base_name
    if faction_name:
        # Don't over-prefix; just hint flavor
        if faction_name.lower() not in base_name.lower():
            name = f"{base_name} ({faction_name})"

    return GeneratedStatBlock(
        name=name,
        size=size,
        kind=kind,
        alignment=alignment,
        armor_class=ac,
        hit_points=hp,
        speed="30 ft",
        str_=s,
        dex=d,
        con=c,
        int_=i,
        wis=w,
        cha=ch,
        proficiency_bonus=proficiency_from_cr(cr),
        attack_bonus=atk,
        save_dc=dc,
        damage_per_round=dpr,
        traits=traits or ["**Keen Instinct.** Advantage on Perception checks that rely on smell or hearing."],
        actions=actions,
    )

def _morale_profile(rng: random.Random, faction_profile: Dict[str, Any], difficulty: str, lethality: int) -> Dict[str, Any]:
    base = int(faction_profile.get("morale_base", 8))
    # difficulty makes opposition slightly braver
    base += {"Easy": -1, "Medium": 0, "Hard": 1, "Deadly": 2}.get(difficulty, 0)
    # lethality makes them more ruthless
    base += 1 if lethality > 70 else 0
    base = max(4, min(12, base))

    triggers = [
        "First ally drops to 0 HP",
        "Leader reduced below half HP",
        "Surrounded or flanked by 2+ enemies",
        "A strong display of magic or fear effect",
        "Objective (loot/ritual) is threatened",
    ]
    rng.shuffle(triggers)
    triggers = triggers[:3]

    outcomes = [
        "Withdraw to better ground and shout warnings",
        "Offer a bargain: safe passage in exchange for something",
        "Surrender if escape routes are cut off",
        "Flee with valuables; abandon the fight",
        "Go reckless for 1 round, then break and run",
    ]
    rng.shuffle(outcomes)

    return {
        "morale_score": base,
        "check": f"Roll 2d6. If the result is greater than morale ({base}), the group breaks.",
        "triggers": triggers,
        "outcomes": outcomes[:3],
    }

def _resolution_paths(rng: random.Random, faction_profile: Dict[str, Any], allow_social: bool) -> List[Dict[str, Any]]:
    paths = []
    # Always include stealth/bypass
    paths.append({"name":"Bypass / Hide", "check":"Stealth vs passive Perception (DC 12–18 by tier)", "result":"Avoid the fight; leave a clue or complication behind."})
    # Parley options
    if allow_social:
        parley = list(faction_profile.get("parley") or ["negotiation"])
        rng.shuffle(parley)
        paths.append({"name":"Parley", "check":f"Persuasion/Deception/Intimidation (DC 13–19 by tier)", "result":f"Offer {parley[0]} to change the encounter's direction."})
    # Bribe
    paths.append({"name":"Bribe / Trade", "check":"Offer valuables or information (no roll) or Persuasion DC 14", "result":"They take the deal and leave—or betray you later."})
    # Tactical withdrawal
    paths.append({"name":"Create an Exit", "check":"Athletics/Acrobatics/Survival DC 14", "result":"You disengage with minimal losses; enemies may pursue later."})
    rng.shuffle(paths)
    return paths[:3]

def _tactical_notes(rng: random.Random, encounter_type: Dict[str, Any], biome_data: Dict[str, Any], faction_profile: Dict[str, Any]) -> List[str]:
    notes = []
    et_name = str(encounter_type.get("name") or "Encounter")
    # Openers
    openers = [
        f"**Opening:** Enemies hesitate for a heartbeat—testing the party before committing.",
        f"**Opening:** They try to isolate a single target and pile on.",
        f"**Opening:** A shouted challenge buys time for positioning.",
        f"**Opening:** They immediately go for alarm/reinforcements rather than damage.",
    ]
    rng.shuffle(openers)
    notes.append(openers[0])

    # Terrain edges
    edges = list(biome_data.get("tactical_edges") or [])
    rng.shuffle(edges)
    if edges:
        notes.append(f"**Terrain:** {edges[0]}. Let players exploit it too.")

    # Faction tactics
    tacts = list(faction_profile.get("tactics") or [])
    rng.shuffle(tacts)
    if tacts:
        notes.append(f"**Enemy Preference:** They favor *{tacts[0]}* if things go their way.")

    # Escalation trigger
    escalations = [
        "If the party makes loud noise, a second wave arrives in 2d4 rounds.",
        "If the leader is threatened, minions risk themselves to create an escape lane.",
        "If the party retreats, the enemies do not chase past a clear boundary—unless provoked.",
        "If the objective is stolen/destroyed, morale checks happen immediately.",
    ]
    rng.shuffle(escalations)
    notes.append(f"**Escalation:** {escalations[0]}")

    # Mistakes
    mistakes = [
        "They underestimate area effects and bunch up early.",
        "They fixate on the toughest-looking character and ignore the backline—at first.",
        "They overcommit to cover; flanking or elevation breaks them.",
        "They assume the party won't fight dirty; a shove/grease/trip surprises them.",
    ]
    rng.shuffle(mistakes)
    notes.append(f"**Likely Mistake:** {mistakes[0]}")

    # Encounter type flavor
    notes.append(f"**Frame:** Treat this as *{et_name}*—the enemies have a job to do, not a death wish.")
    return notes

def _environment_complications(rng: random.Random, biome_data: Dict[str, Any], encounter_type_id: str) -> List[Dict[str, Any]]:
    comps = _pick_biome_complications(rng, biome_data, count=2)
    out = []
    for c in comps:
        # Attach mechanics
        if c.lower() in ("low light", "low visibility", "sudden fog"):
            out.append({"name":c, "trigger":"Always", "effect":"Disadvantage on Perception checks relying on sight beyond 30 ft; ranged attacks beyond 60 ft are at disadvantage.", "counterplay":"Light sources, blindsight, close distance."})
        elif "mud" in c.lower():
            out.append({"name":c, "trigger":"Moving through marked areas", "effect":"Difficult terrain; DC 13 Strength (Athletics) to avoid being slowed further (0 ft) for one round.", "counterplay":"Jump, rope, avoid zones."})
        elif "alarm" in c.lower() or "echo" in c.lower():
            out.append({"name":c, "trigger":"Loud noises or missed attack vs metal/stone", "effect":"Reinforcements arrive in 2d4 rounds (or the encounter shifts position).", "counterplay":"Silence, quick takedown, stealth."})
        elif "bystander" in c.lower() or "crowd" in c.lower():
            out.append({"name":c, "trigger":"Any AoE or obvious violence", "effect":"Collateral risk: on a natural 1–2 on an attack roll, a bystander is threatened; party can spend an action to prevent harm.", "counterplay":"Relocation, intimidation, nonlethal tactics."})
        else:
            out.append({"name":c, "trigger":"On initiative count 20 (losing ties)", "effect":"A minor hazard shifts the map (falling debris, gust, surge). Each creature makes DC 13 Dex save or takes 1d6 damage and is pushed 5 ft.", "counterplay":"Take cover, brace, move to safe zones."})
    return out

def _make_title(rng: random.Random, faction_name: str, encounter_type_name: str, biome: str) -> str:
    hooks = [
        "Nervous", "Hungry", "Desperate", "Overconfident", "Bleeding", "Rattled", "Watchful",
        "Silent", "Ruthless", "Cornered", "Focused"
    ]
    noun = [
        "Patrol", "Raid", "Ritual", "Checkpoint", "Ambush", "Scavengers", "Pursuit", "Standoff", "Operation"
    ]
    h = rng.choice(hooks)
    n = rng.choice(noun)
    if encounter_type_name:
        n = encounter_type_name.split("/")[0].strip()
    if faction_name:
        return f"{h} {faction_name} {n} ({biome})"
    return f"{h} {n} ({biome})"

def generate_encounter(
    ctx,
    tables_dir: Path,
    inputs: EncounterInputs,
    iteration: int,
) -> EncounterResult:
    tables = load_tables(tables_dir)

    # Deterministic RNG
    if inputs.lock_seed:
        seed_used = int(inputs.seed or 0) or ctx.derive_seed("encounters", "locked")
        rng = random.Random(seed_used)
    else:
        seed_used = ctx.derive_seed("encounters", "generate", iteration, inputs.party_level, inputs.biome, inputs.faction, inputs.encounter_type)
        rng = random.Random(seed_used)

    biome_data = (tables["biomes"] or {}).get(inputs.biome) or {}
    encounter_type = _pick_encounter_type(rng, tables, inputs.biome, inputs.encounter_type)
    faction_profile = _pick_faction_profile(rng, tables, inputs.faction_profile)

    faction_name = inputs.faction.strip() or str(faction_profile.get("name") or "Opposition")
    et_id = str(encounter_type.get("id") or "patrol")
    et_name = str(encounter_type.get("name") or "Encounter")

    budget = threat_budget(inputs.party_level, inputs.party_size, inputs.difficulty, inputs.party_condition, inputs.lethality)
    desired_roles = _pick_role_mix(rng, et_id, inputs.allow_social, inputs.allow_hazard)

    candidates = _candidate_monsters(tables, inputs.biome, faction_profile)
    picks = _pick_monsters_for_budget(rng, candidates, inputs.party_level, budget, desired_roles)

    # Statblocks (one per pick entry)
    statblocks: List[GeneratedStatBlock] = []
    for p in picks:
        statblocks.append(_make_statblock(rng, p.name, p.kind, p.cr, p.role, faction_name))

    morale = _morale_profile(rng, faction_profile, inputs.difficulty, inputs.lethality)
    env = _environment_complications(rng, biome_data, et_id)
    tactics = _tactical_notes(rng, encounter_type, biome_data, faction_profile)
    resolution = _resolution_paths(rng, faction_profile, inputs.allow_social)

    # Situation frame
    situation_frames = [
        "They are **here for a reason** (orders, hunger, fear, greed). If the party changes that reason, the encounter changes.",
        "This is a **pressure scene**, not a slugfest. Enemies will retreat, bargain, or escalate based on morale and objectives.",
        "Someone is **buying time** (for reinforcements, for an escape, for a ritual). Track rounds and let that clock matter.",
        "This area has **a job**: guard, harvest, smuggle, worship, hunt. Lean into that job for improvisation and clues.",
    ]
    rng.shuffle(situation_frames)
    situation = situation_frames[0]

    title = _make_title(rng, faction_name, et_name, inputs.biome)

    # Markdown assembly
    tags = ["Encounter", inputs.biome]
    if inputs.dungeon_tag.strip():
        tags.append(f"Dungeon:{inputs.dungeon_tag.strip()}")
    if faction_name:
        tags.append(f"Faction:{faction_name}")

    md_lines: List[str] = []
    md_lines.append(f"# Encounter: {title}")
    md_lines.append("")
    md_lines.append(f"**Biome:** {inputs.biome}  ")
    md_lines.append(f"**Dungeon Tag:** {inputs.dungeon_tag or '—'}  ")
    md_lines.append(f"**Faction:** {faction_name}  ")
    md_lines.append(f"**Encounter Type:** {et_name}  ")
    md_lines.append(f"**Party:** Level {inputs.party_level} × {inputs.party_size} ({inputs.party_condition})  ")
    md_lines.append(f"**Difficulty Intent:** {inputs.difficulty}  ")
    md_lines.append(f"**Seed:** `{seed_used}`")
    if inputs.notes.strip():
        md_lines.append("")
        md_lines.append(f"> **GM Intent:** {inputs.notes.strip()}")
    md_lines.append("")
    md_lines.append("## Situation")
    md_lines.append(situation)
    md_lines.append("")
    md_lines.append("## Opposition")
    md_lines.append(f"Threat Budget (internal): **{budget}** points")
    md_lines.append("")
    for p in picks:
        md_lines.append(f"- **{p.count}× {p.name}** — {p.kind}, role: *{p.role}*, CR {p.cr:g}")
    md_lines.append("")
    md_lines.append("## Tactical Notes")
    for n in tactics:
        md_lines.append(f"- {n}")
    md_lines.append("")
    md_lines.append("## Morale")
    md_lines.append(f"**Morale Score:** {morale['morale_score']} (2–12)  ")
    md_lines.append(morale["check"])
    md_lines.append("")
    md_lines.append("**Triggers**")
    for t in morale["triggers"]:
        md_lines.append(f"- {t}")
    md_lines.append("")
    md_lines.append("**Outcomes on a break**")
    for o in morale["outcomes"]:
        md_lines.append(f"- {o}")
    md_lines.append("")
    md_lines.append("## Environmental Complications")
    for c in env:
        md_lines.append(f"### {c['name']}")
        md_lines.append(f"- **Trigger:** {c['trigger']}")
        md_lines.append(f"- **Effect:** {c['effect']}")
        md_lines.append(f"- **Counterplay:** {c['counterplay']}")
        md_lines.append("")
    md_lines.append("## Resolution Paths")
    for rp in resolution:
        md_lines.append(f"- **{rp['name']}** — {rp['check']} → {rp['result']}")
    md_lines.append("")
    md_lines.append("## Player-Facing Cues")
    cues = list(biome_data.get("sensory_cues") or [])
    rng.shuffle(cues)
    cues = cues[:3] if cues else ["Something is off.", "You hear movement.", "The air feels wrong."]
    for c in cues:
        md_lines.append(f"- {c}")
    md_lines.append("")

    md_lines.append("## Stat Blocks (Quick)")
    md_lines.append("> These are generator-friendly blocks meant for fast play. Swap to official blocks as desired.")
    md_lines.append("")
    for sb in statblocks:
        md_lines.append(f"### {sb.name}")
        md_lines.append(f"*{sb.size} {sb.kind}, {sb.alignment}*")
        md_lines.append(f"- **AC** {sb.armor_class}  **HP** {sb.hit_points}  **Speed** {sb.speed}")
        md_lines.append(f"- **STR** {sb.str_}  **DEX** {sb.dex}  **CON** {sb.con}  **INT** {sb.int_}  **WIS** {sb.wis}  **CHA** {sb.cha}")
        md_lines.append(f"- **PB** +{sb.proficiency_bonus}  **Atk** +{sb.attack_bonus}  **Save DC** {sb.save_dc}")
        md_lines.append("")
        md_lines.append("**Traits**")
        for tr in sb.traits:
            md_lines.append(f"- {tr}")
        md_lines.append("")
        md_lines.append("**Actions**")
        for act in sb.actions:
            md_lines.append(f"- {act}")
        md_lines.append("")

    markdown = "\n".join(md_lines)

    return EncounterResult(
        title=title,
        seed_used=seed_used,
        created_ts=time.time(),
        inputs=asdict(inputs),
        opposition=[asdict(p) for p in picks],
        statblocks=[asdict(sb) for sb in statblocks],
        markdown=markdown,
        tags=tags,
    )
