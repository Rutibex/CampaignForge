from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any, List, Optional, Tuple
import importlib.resources as pkgres
import json
import random

# --- table loading ---

def _load_table(name: str) -> Any:
    """
    Load a JSON table from tables/<name>.json inside this package.
    """
    try:
        data = pkgres.files(__package__).joinpath("tables").joinpath(f"{name}.json").read_text(encoding="utf-8")
        return json.loads(data)
    except Exception:
        return None

_TABLE_CACHE: Dict[str, Any] = {}

def table(name: str) -> Any:
    if name not in _TABLE_CACHE:
        _TABLE_CACHE[name] = _load_table(name)
    return _TABLE_CACHE[name]

# --- config/result ---

TIERS = ["Relic", "Lesser Artifact", "Major Artifact", "Mythic Artifact"]

@dataclass
class ArtifactGenConfig:
    tier: str = "Major Artifact"
    theme: str = "Random"
    include_sentience: bool = True
    fixed_dc: bool = True
    base_dc: int = 17
    ability_mod: str = "Charisma"   # only used if fixed_dc is False
    num_minor: int = 3
    num_major: int = 2
    include_drawback: bool = True
    include_destruction: bool = True
    include_awakening: bool = True

# --- helpers ---

def _pick(rng: random.Random, items: List[Any]) -> Any:
    return items[rng.randrange(0, len(items))]

def _maybe(rng: random.Random, p: float) -> bool:
    return rng.random() < p

def _dc_text(cfg: ArtifactGenConfig, tier: str) -> Tuple[int, str]:
    """
    Returns (suggested_dc, display_text).
    """
    tier_defaults = {
        "Relic": 13,
        "Lesser Artifact": 15,
        "Major Artifact": 17,
        "Mythic Artifact": 19,
    }
    dc = int(cfg.base_dc) if cfg.fixed_dc else int(tier_defaults.get(tier, 15))
    if cfg.fixed_dc:
        return dc, f"DC {dc}"
    # Formula-based (5e-ish, transparent)
    # Many tables use 'spell save DC' wording; we keep it simple.
    return dc, f"Spell save DC = 8 + your proficiency bonus + your {cfg.ability_mod} modifier (suggested DC {dc})"

def _tier_power_budget(tier: str) -> Tuple[int, int]:
    # (minor, major) suggestion
    if tier == "Relic":
        return (2, 1)
    if tier == "Lesser Artifact":
        return (3, 1)
    if tier == "Major Artifact":
        return (3, 2)
    return (4, 3)

def _name(rng: random.Random) -> Tuple[str, str]:
    adj = _pick(rng, table("adjectives") or ["Forgotten"])
    noun = _pick(rng, table("nouns") or ["Relic"])
    epithet = _pick(rng, table("epithets") or ["Of Uncertain Purpose"])
    return f"The {adj} {noun}", epithet

def _physical(rng: random.Random) -> Dict[str, str]:
    form = _pick(rng, table("forms") or ["relic"])
    material = _pick(rng, table("materials") or ["strange metal"])
    quirk = _pick(rng, table("quirks") or ["feels wrong to hold"])
    return {"form": form, "material": material, "quirk": quirk}

def _origin(rng: random.Random) -> str:
    return _pick(rng, table("origins") or ["made long ago for unknown reasons"])

def _status(rng: random.Random) -> str:
    return _pick(rng, table("statuses") or ["Lost"])

def _theme(rng: random.Random, cfg: ArtifactGenConfig) -> str:
    if cfg.theme and cfg.theme != "Random":
        return cfg.theme
    return _pick(rng, table("themes") or ["Oaths"])

def _attunement(rng: random.Random, tier: str) -> Dict[str, Any]:
    req = _pick(rng, table("attunement_requirements") or ["Attunement required."])
    special = ""
    if tier in ("Major Artifact", "Mythic Artifact") and _maybe(rng, 0.65):
        special = _pick(rng, [
            "While attuned, the artifact subtly judges you. If you act against its nature, it may withhold power at the GM’s discretion.",
            "If you willingly violate the attunement requirement, you immediately lose attunement and suffer a backlash (see Drawback).",
            "The artifact’s mark cannot be hidden by mundane means while you remain attuned.",
        ])
    return {"required": True, "requirement": req, "special": special}

def _sentience(rng: random.Random) -> Optional[Dict[str, Any]]:
    p = _pick(rng, table("personalities") or [{"axis":"Curious","desires":["stories"],"voice":["whisper"]}])
    alignment = _pick(rng, ["lawful","neutral","chaotic"]) + " " + _pick(rng, ["good","neutral","evil"])
    comm = _pick(rng, ["whispers in your mind","writes in condensation on nearby surfaces","speaks through reflections","sings in harmonics only you can hear"])
    return {
        "axis": p.get("axis","Curious"),
        "desires": list(p.get("desires",[]))[:3],
        "voice": _pick(rng, p.get("voice",["whisper"])),
        "alignment": alignment,
        "communication": comm,
        "contested_checks": "When you attempt to use a Major power, the GM may call for a Charisma (Persuasion/Intimidation) check opposed by the artifact’s Charisma (DC 15–19 depending on tier) if you are acting against its desires."
    }

def _faction(rng: random.Random) -> Dict[str, str]:
    adj = _pick(rng, table("faction_adjs") or ["Grey"])
    noun = _pick(rng, table("faction_nouns") or ["Society"])
    ftype = _pick(rng, table("faction_types") or ["Order"])
    motive = _pick(rng, table("faction_motives") or ["to obtain it"])
    name = f"The {adj} {noun}"
    return {"name": name, "type": ftype, "motive": motive}

def _rumor(rng: random.Random, name: str) -> str:
    tpl = _pick(rng, table("rumor_templates") or ["They say {name} is cursed."])
    return str(tpl).replace("{name}", name)

def _history(rng: random.Random) -> List[str]:
    base = table("history_events") or []
    if not base:
        return ["It has been lost, found, and lost again."]
    # pick 2–4 unique-ish
    k = rng.randrange(2, 5)
    out = []
    for _ in range(k):
        out.append(_pick(rng, base))
    # de-dupe preserving order
    seen=set()
    uniq=[]
    for h in out:
        if h in seen: 
            continue
        seen.add(h); uniq.append(h)
    return uniq

def _hooks(rng: random.Random, artifact_name: str) -> Dict[str, Any]:
    want = [_faction(rng) for _ in range(3)]
    fear = [_faction(rng) for _ in range(2)]
    misunderstand = _faction(rng)
    rumors = [_rumor(rng, artifact_name) for _ in range(4)]
    return {
        "factions_want": want,
        "factions_fear": fear,
        "faction_misunderstands": misunderstand,
        "rumors": rumors,
        "history": _history(rng)
    }


# --- power templates ---

# Each template returns (name, rules_text, tags)
# We keep these intentionally exotic but rules-legal.
def _tpl_silence(rng, cfg, tier, theme, dc_text):
    rng_range = _pick(rng, (table("ranges") or ["30 feet"]))
    dur = _pick(rng, (table("durations") or ["1 minute"]))
    dc = dc_text
    cost = _pick(rng, (table("costs") or ["you gain 1 level of exhaustion"]))
    return ("Canticle of Stolen Words",
            f"As a reaction when a creature you can see within {rng_range} would speak or provide a verbal component, you may silence it. "
            f"The creature must succeed on a Constitution saving throw ({dc}) or be unable to speak for {dur}. "
            f"A silenced creature can still communicate via gestures, but it cannot cast spells with verbal components.\n\n"
            f"**Cost:** {cost}.",
            ["control","silence","reaction"])

def _tpl_shadow_servant(rng, cfg, tier, theme, dc_text):
    dur = _pick(rng, ["1 minute","10 minutes","1 hour"])
    cost = _pick(rng, (table("costs") or ["you gain 1 level of exhaustion"]))
    return ("Shadow Unfurling",
            f"When you reduce a creature to 0 hit points, you can tear free its shadow. The shadow becomes a **shadow servant** until the end of {dur}. "
            f"As a bonus action, you can command it to move up to 30 feet and take one of these actions: Help, Disengage, Dash, or Deliver. "
            f"**Deliver:** The shadow makes a melee spell attack (+{_pick(rng,[6,7,8,9,10])}) against a creature within 5 feet; on a hit it deals 2d6 necrotic damage.\n\n"
            f"**Cost:** {cost}.",
            ["summon","shadow","bonus action"])

def _tpl_mirror_step(rng, cfg, tier, theme, dc_text):
    rng_range = _pick(rng, ["30 feet","60 feet","90 feet"])
    cost = _pick(rng, (table("costs") or ["you gain 1 level of exhaustion"]))
    return ("Mirror-Step",
            f"As a bonus action, you teleport up to {rng_range} to an unoccupied space you can see. "
            f"Until the end of your current turn, you have advantage on the next attack roll you make and you do not provoke opportunity attacks.\n\n"
            f"**Cost:** {cost}.",
            ["mobility","teleport","bonus action"])

def _tpl_time_lapse(rng, cfg, tier, theme, dc_text):
    rng_range = _pick(rng, ["30 feet","60 feet"])
    dur = _pick(rng, ["until the end of your next turn","for 1 minute"])
    cost = _pick(rng, (table("costs") or ["you gain 1 level of exhaustion"]))
    return ("Lapse of the Second Hand",
            f"As an action, choose one creature you can see within {rng_range}. It must succeed on a Wisdom saving throw ({dc_text}) or be **slowed** for {dur}. "
            f"While slowed, the creature’s speed is halved, it can’t take reactions, and on its turn it can take either an action or a bonus action (not both). "
            f"If the creature attempts to cast a spell with a casting time of 1 action, roll a d20; on 11 or higher the spell doesn’t take effect until the creature’s next turn.\n\n"
            f"**Cost:** {cost}.",
            ["control","time","action"])

def _tpl_oath_chain(rng, cfg, tier, theme, dc_text):
    rng_range=_pick(rng, ["30 feet","60 feet"])
    dur=_pick(rng, ["1 minute","10 minutes"])
    cost=_pick(rng, (table("costs") or ["you gain 1 level of exhaustion"]))
    return ("Chain of the Sworn",
            f"As an action, speak an oath (one sentence) and choose up to two creatures you can see within {rng_range}. "
            f"Each target must succeed on a Charisma saving throw ({dc_text}) or become **bound** to that oath for {dur}. "
            f"While bound, if a target knowingly acts directly against the oath, it takes 4d6 psychic damage and must immediately succeed on a Wisdom saving throw ({dc_text}) or be stunned until the end of its next turn. "
            f"Once you bind creatures in this way, you can't do so again until you finish a long rest.\n\n"
            f"**Cost:** {cost}.",
            ["oath","bind","action"])

def _tpl_storm_lantern(rng, cfg, tier, theme, dc_text):
    rng_range=_pick(rng, ["60 feet","90 feet","120 feet"])
    dur=_pick(rng, ["1 minute","10 minutes"])
    dtype=_pick(rng, (table("damage_types") or ["force"]))
    cost=_pick(rng, (table("costs") or ["you gain 1 level of exhaustion"]))
    return ("Lantern of Calling Weather",
            f"As an action, you create a 20-foot-radius sphere of turbulent air centered on a point you can see within {rng_range} for {dur}. "
            f"The area is difficult terrain for creatures other than you. When a creature enters the area for the first time on a turn or starts its turn there, "
            f"it must make a Strength saving throw ({dc_text}). On a failed save, it takes 3d8 {dtype} damage and is pushed 10 feet away from the center; "
            f"on a successful save, it takes half damage and isn't pushed.\n\n"
            f"**Cost:** {cost}.",
            ["zone","storm","action"])

def _tpl_memory_tax(rng, cfg, tier, theme, dc_text):
    rng_range=_pick(rng, ["touch","30 feet"])
    dur=_pick(rng, ["1 hour","24 hours","until you finish a long rest"])
    cost=_pick(rng, (table("costs") or ["you gain 1 level of exhaustion"]))
    return ("Mnemonic Levy",
            f"As an action, choose one creature within {rng_range}. It must succeed on an Intelligence saving throw ({dc_text}) or lose access to one memory thread for {dur}. "
            f"Choose one: **a language**, **a proficiency**, or **a known spell of 3rd level or lower**. The target can’t use the chosen option for the duration. "
            f"At the end of the duration, the memory returns.\n\n"
            f"**Cost:** {cost}.",
            ["debuff","memory","action"])

def _tpl_grave_warrant(rng, cfg, tier, theme, dc_text):
    rng_range=_pick(rng, ["30 feet","60 feet"])
    dur=_pick(rng, ["1 minute","10 minutes"])
    cost=_pick(rng, (table("costs") or ["you gain 1 level of exhaustion"]))
    return ("Warrant of the Grave",
            f"As a bonus action, you mark a creature you can see within {rng_range} for {dur}. "
            f"Until the mark ends, the first time each turn you deal damage to the target, it takes an extra 2d6 necrotic damage. "
            f"If the target drops to 0 hit points while marked, you immediately regain one expended Hit Die.\n\n"
            f"**Cost:** {cost}.",
            ["mark","necrotic","bonus action"])

def _tpl_refusal_aegis(rng, cfg, tier, theme, dc_text):
    dur=_pick(rng, ["until the start of your next turn","for 1 minute"])
    cost=_pick(rng, (table("costs") or ["you gain 1 level of exhaustion"]))
    return ("Aegis of Refusal",
            f"When a creature you can see targets you with an attack, you can use your reaction to invoke an impossible 'no'. "
            f"Until {dur}, you gain a +5 bonus to AC, including against the triggering attack. "
            f"If the triggering attack misses, you can push the attacker 10 feet away.\n\n"
            f"**Cost:** {cost}.",
            ["defense","reaction"])

_MINOR_TEMPLATES = [
    _tpl_mirror_step,
    _tpl_grave_warrant,
    _tpl_refusal_aegis,
]
_MAJOR_TEMPLATES = [
    _tpl_oath_chain,
    _tpl_silence,
    _tpl_shadow_servant,
    _tpl_time_lapse,
    _tpl_storm_lantern,
    _tpl_memory_tax,
]

def _drawback(rng: random.Random, tier: str, theme: str) -> str:
    # Strong drawbacks for strong tiers
    options = [
        "The artifact is jealous. While attuned, you have disadvantage on Persuasion checks made to request aid from strangers; they sense something 'claimed' about you.",
        "The artifact drinks certainty. When you roll a natural 1 on an attack roll, ability check, or saving throw, you take 2d6 psychic damage and your speed becomes 0 until the end of your next turn.",
        "The artifact cannot tolerate peace. If you go 24 hours without taking damage from a hostile creature, you gain 1 level of exhaustion at the next dawn.",
        "The artifact attracts omens. Animals behave strangely around you, and you can’t benefit from being hidden by mundane means in natural environments.",
        "The artifact taxes your body. After you use any Major power, you must succeed on a DC 15 Constitution saving throw or gain 1 level of exhaustion.",
        "The artifact remembers the dead. Each time you finish a long rest, roll a d20; on a 1, you wake with the last words of someone you killed on your lips and can’t speak above a whisper for 1 hour.",
        "The artifact demands narrative symmetry. If you accept a gift worth 50 gp or more, you must give away an equivalent value before your next long rest or you lose access to one Minor property (GM chooses) until you do."
    ]
    return _pick(rng, options)

def _destruction(rng: random.Random, theme: str) -> str:
    options = [
        "It can be destroyed only by being willingly discarded at the exact location where it was first claimed, during a thunderstorm, while its bearer speaks a true apology.",
        "It can be destroyed only if it is used to save the life of a sworn enemy, and the bearer then dies within 24 hours.",
        "It can be destroyed only by being submerged in holy water for 7 days while a lullaby is sung by someone who genuinely loves the bearer.",
        "It can be destroyed only if its true name is etched into a gravestone that has never held a body, and then that stone is shattered under moonlight.",
        "It can be destroyed only by forging it into a mundane tool and using that tool every day for a year without ever drawing blood."
    ]
    return _pick(rng, options)

def _awakening(rng: random.Random, tier: str, theme: str) -> Dict[str, Any]:
    triggers = [
        "Slay a legendary creature whose ideals oppose the artifact’s nature.",
        "Break an oath that you truly believed in (the artifact grows stronger from the fracture).",
        "Carry the artifact through a planar boundary and return with it intact.",
        "Spend 30 days attuned without ever using a Major power (patience is rewarded).",
        "Use the artifact to spare the life of someone who deserves death (by your own standards)."
    ]
    upgrades = [
        "One Minor power becomes at-will (no recharge), but its Cost triggers on each use.",
        "Increase the damage of one power by one die size (d6→d8, etc.) and increase its Cost severity.",
        "The artifact gains a new 'aura' effect in a 10-foot radius aligned with its theme.",
        "You gain resistance to one damage type, but you gain vulnerability to another (chosen by the GM).",
        "Your spell save DC for artifact powers increases by 1, but the artifact’s drawback becomes unavoidable once per day."
    ]
    return {
        "trigger": _pick(rng, triggers),
        "upgrade": _pick(rng, upgrades)
    }

def generate_artifact(rng: random.Random, cfg: ArtifactGenConfig) -> Dict[str, Any]:
    tier = cfg.tier if cfg.tier in TIERS else "Major Artifact"
    theme = _theme(rng, cfg)
    name, epithet = _name(rng)
    phys = _physical(rng)
    origin = _origin(rng)
    status = _status(rng)
    attune = _attunement(rng, tier)

    # Power budget defaults per tier if cfg is 0
    sug_minor, sug_major = _tier_power_budget(tier)
    num_minor = max(0, int(cfg.num_minor or sug_minor))
    num_major = max(0, int(cfg.num_major or sug_major))

    suggested_dc, dc_text = _dc_text(cfg, tier)

    minor_props = []
    for _ in range(num_minor):
        tpl = _pick(rng, _MINOR_TEMPLATES)
        minor_props.append({
            "name": tpl(rng, cfg, tier, theme, dc_text)[0],
            "text": tpl(rng, cfg, tier, theme, dc_text)[1],
            "tags": tpl(rng, cfg, tier, theme, dc_text)[2],
        })

    major_powers = []
    for _ in range(num_major):
        tpl = _pick(rng, _MAJOR_TEMPLATES)
        # Add recharge
        recharge = _pick(rng, (table("recharge") or ["(1/Long Rest)"]))
        nm, txt, tags = tpl(rng, cfg, tier, theme, dc_text)
        major_powers.append({"name": f"{nm} {recharge}", "text": txt, "tags": tags})

    drawback = _drawback(rng, tier, theme) if cfg.include_drawback else ""
    destruction = _destruction(rng, theme) if cfg.include_destruction else ""
    sentience = _sentience(rng) if (cfg.include_sentience and tier in ("Major Artifact","Mythic Artifact") and _maybe(rng, 0.85)) else None
    awakening = _awakening(rng, tier, theme) if (cfg.include_awakening and tier in ("Lesser Artifact","Major Artifact","Mythic Artifact")) else None

    hooks = _hooks(rng, name)

    return {
        "version": 1,
        "name": name,
        "epithet": epithet,
        "tier": tier,
        "theme": theme,
        "form": phys["form"],
        "material": phys["material"],
        "quirk": phys["quirk"],
        "origin": origin,
        "status": status,
        "attunement": attune,
        "dc_suggested": suggested_dc,
        "dc_text": dc_text,
        "minor_properties": minor_props,
        "major_powers": major_powers,
        "drawback": drawback,
        "destruction": destruction,
        "sentience": sentience,
        "awakening": awakening,
        "hooks": hooks,
    }

def artifact_to_markdown(a: Dict[str, Any], for_players: bool = False) -> str:
    """
    GM markdown includes costs/drawbacks; player version omits or softens them.
    """
    lines: List[str] = []
    lines.append(f"# {a.get('name','Artifact')}")
    lines.append(f"*{a.get('epithet','')}*")
    lines.append("")
    lines.append(f"**Tier:** {a.get('tier','')}")
    lines.append(f"**Theme:** {a.get('theme','')}")
    lines.append(f"**Form:** {a.get('form','')}")
    lines.append(f"**Material:** {a.get('material','')}")
    lines.append(f"**Telltale Quirk:** {a.get('quirk','')}")
    lines.append("")
    lines.append(f"**Origin:** {a.get('origin','')}")
    lines.append(f"**Current Status:** {a.get('status','')}")
    lines.append("")
    att = a.get("attunement", {}) or {}
    lines.append("## Attunement")
    lines.append("Attunement required.")
    if att.get("requirement"):
        lines.append(att["requirement"])
    if att.get("special") and not for_players:
        lines.append("")
        lines.append(f"**GM Note:** {att['special']}")
    lines.append("")
    lines.append("## Minor Properties")
    for p in a.get("minor_properties", []) or []:
        lines.append(f"### {p.get('name','Property')}")
        txt = p.get("text","").strip()
        if for_players:
            # Keep the cool, but soften explicit costs if present.
            txt = txt.replace("**Cost:**", "**Price:**")
        lines.append(txt)
        lines.append("")
    lines.append("## Major Powers")
    for p in a.get("major_powers", []) or []:
        lines.append(f"### {p.get('name','Power')}")
        txt = p.get("text","").strip()
        if for_players:
            # In player handout, conceal the precise cost occasionally.
            txt = txt.replace("**Cost:**", "**Price:**")
            # Remove severe spoilers
            txt = txt.replace("Hit Die (permanently)", "Hit Die")
        lines.append(txt)
        lines.append("")
    if a.get("sentience") and not for_players:
        s = a["sentience"]
        lines.append("## Sentience")
        lines.append(f"**Disposition:** {s.get('axis','')}")
        lines.append(f"**Alignment Tendency:** {s.get('alignment','')}")
        lines.append(f"**Voice:** {s.get('voice','')}")
        lines.append(f"**Communication:** {s.get('communication','')}")
        lines.append("")
        lines.append("**Desires:**")
        for d in s.get("desires", []) or []:
            lines.append(f"- {d}")
        lines.append("")
        lines.append(s.get("contested_checks",""))
        lines.append("")
    if a.get("drawback"):
        lines.append("## Drawback")
        if for_players:
            # Hint, don't fully reveal
            lines.append("The artifact takes something in return. The GM will reveal the exact price through play.")
        else:
            lines.append(a["drawback"])
        lines.append("")
    if a.get("awakening"):
        aw = a["awakening"]
        lines.append("## Awakening")
        lines.append(f"**Trigger:** {aw.get('trigger','')}")
        lines.append(f"**Upgrade:** {aw.get('upgrade','')}")
        lines.append("")
    hooks = a.get("hooks") or {}
    if hooks:
        if not for_players:
            lines.append("## Rumors")
            for r in hooks.get("rumors", []) or []:
                lines.append(f"- {r}")
            lines.append("")
            lines.append("## History")
            for h in hooks.get("history", []) or []:
                lines.append(f"- {h}")
            lines.append("")
            lines.append("## Factions")
            lines.append("**They want it:**")
            for f in hooks.get("factions_want", []) or []:
                lines.append(f"- **{f.get('name','Faction')}** ({f.get('type','')}) — {f.get('motive','')}")
            lines.append("")
            lines.append("**They fear it:**")
            for f in hooks.get("factions_fear", []) or []:
                lines.append(f"- **{f.get('name','Faction')}** ({f.get('type','')}) — {f.get('motive','')}")
            lines.append("")
            mis = hooks.get("faction_misunderstands") or {}
            if mis:
                lines.append("**They misunderstand it:**")
                lines.append(f"- **{mis.get('name','Faction')}** ({mis.get('type','')}) — {mis.get('motive','')}")
                lines.append("")
        else:
            # Players get 1–2 rumors max
            rumors = list(hooks.get("rumors", []) or [])
            if rumors:
                lines.append("## Rumors")
                lines.append(f"- {rumors[0]}")
                if len(rumors) > 1:
                    lines.append(f"- {rumors[1]}")
                lines.append("")

    if a.get("destruction") and not for_players:
        lines.append("## Destruction")
        lines.append(a["destruction"])
        lines.append("")
    return "\n".join(lines).strip() + "\n"
