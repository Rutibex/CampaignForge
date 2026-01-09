from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Any
import re
import time
import uuid
import random


def slugify(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"[^a-z0-9\-_ ]+", "", s)
    s = re.sub(r"\s+", "_", s)
    s = re.sub(r"_+", "_", s)
    return s[:48] or "faction"


def ensure_unique_id(existing: Sequence[str], desired: str) -> str:
    """Return a unique id, suffixing with _2/_3/... if needed."""
    base = slugify(desired) or "faction"
    taken = set(x for x in existing if x)
    if base not in taken:
        return base
    i = 2
    while True:
        cand = f"{base}_{i}"
        if cand not in taken:
            return cand
        i += 1


def generate_factions_batch(rng: random.Random, *, count: int, richness: int = 2) -> List[Dict[str, Any]]:
    """Generate multiple factions and auto-wire relationships between them.

    richness: 1=Light, 2=Standard, 3=Heavy
    """
    count = max(2, int(count))
    richness = max(1, min(3, int(richness or 2)))

    factions: List[Dict[str, Any]] = []

    # Step 1: create factions with extra content based on richness
    for i in range(count):
        frng = random.Random(rng.randrange(1 << 30))
        f = generate_faction(frng)

        # Enrich content
        if richness == 1:
            # trim down
            f["goals"] = f.get("goals", [])[:2]
            f["assets"] = f.get("assets", [])[:2]
            f["timeline"] = f.get("timeline", [])[:1]
        elif richness == 2:
            # standard: ensure at least a baseline
            while len(f.get("goals", [])) < 3:
                f.setdefault("goals", []).append(generate_goal(frng))
            while len(f.get("assets", [])) < 3:
                f.setdefault("assets", []).append(generate_asset(frng))
            while len(f.get("timeline", [])) < 2:
                f.setdefault("timeline", []).append(generate_timeline_event(frng, f.get("name", "Faction")))
            if frng.random() < 0.35 and not f.get("schisms"):
                f.setdefault("schisms", []).append(generate_schism(frng))
        else:
            # heavy
            while len(f.get("goals", [])) < 5:
                f.setdefault("goals", []).append(generate_goal(frng))
            while len(f.get("assets", [])) < 6:
                f.setdefault("assets", []).append(generate_asset(frng))
            while len(f.get("timeline", [])) < 4:
                f.setdefault("timeline", []).append(generate_timeline_event(frng, f.get("name", "Faction")))
            if not f.get("schisms"):
                f.setdefault("schisms", []).append(generate_schism(frng))

        factions.append(f)

    # Step 2: build a relationship web
    # We'll ensure each faction has at least 2 links, and then add a few extra.
    names = [f.get("name", "Faction") for f in factions]
    for idx, f in enumerate(factions):
        rels: List[Dict[str, Any]] = []

        # pick a few unique other indices
        others = [j for j in range(count) if j != idx]
        rng.shuffle(others)
        min_links = 2 if count >= 3 else 1
        max_links = min(len(others), min_links + (richness - 1) + rng.randint(0, 1 + richness))
        chosen = others[:max_links]

        for j in chosen:
            rel_type = rng.choice(REL_TYPES)
            tension = str(rng.randint(1, 6))
            rels.append({
                "id": str(uuid.uuid4()),
                "type": rel_type,
                "target": names[j],
                "tension": tension,
                "history": "",
            })

        f["relationships"] = rels

    # Step 3: add reciprocal links where missing
    name_to_idx = {f.get("name"): i for i, f in enumerate(factions)}
    for f in factions:
        src_name = f.get("name")
        for rel in list(f.get("relationships", []) or []):
            tgt = rel.get("target")
            if tgt not in name_to_idx:
                continue
            tgt_f = factions[name_to_idx[tgt]]
            tgt_rels = tgt_f.setdefault("relationships", [])
            # check if reciprocal already exists
            if any(r.get("target") == src_name for r in tgt_rels):
                continue
            tgt_rels.append({
                "id": str(uuid.uuid4()),
                "type": reciprocal_relationship(rel.get("type", "Rival")),
                "target": src_name,
                "tension": rel.get("tension", "3"),
                "history": "",
            })

    return factions


def now_iso() -> str:
    # local wall time is fine for notes
    return time.strftime("%Y-%m-%dT%H:%M:%S")


# ---- lightweight tables (expand later / allow external packs later) ----

FACTION_TYPES = [
    "Guild", "Thieves' Syndicate", "Cult", "Noble House", "Mercenary Company",
    "Knightly Order", "Mage Cabal", "Temple", "Trade Consortium", "Tribe",
    "Rebel Cell", "Imperial Office", "Explorers' League", "Smugglers' Ring",
]

ETHOS = [
    "Pragmatic survival", "Apocalyptic zeal", "Profit above all", "Honor-bound duty",
    "Secret knowledge", "Purity and control", "Joyful chaos", "Law and order",
    "Blood and lineage", "Revenge and restitution", "The old ways", "Progress at any cost",
]

GOAL_TEMPLATES = [
    ("Expansion", "Seize control of {thing} in {place}."),
    ("Acquisition", "Acquire the {relic} before rivals do."),
    ("Suppression", "Eliminate witnesses tied to {secret}."),
    ("Control", "Install a loyal agent within {place}."),
    ("Survival", "Secure a new source of {resource} to avoid collapse."),
    ("Revelation", "Uncover the truth behind {mystery}."),
]

THINGS = ["the river crossings", "the guildhall district", "the old catacombs", "the northern road", "the salt mines", "the oracle shrine"]
PLACES = ["Blackbridge", "the Lantern Ward", "Greyfen", "the Ruined March", "the Chalk Hills", "Port Lark"]
RELICS = ["Gloam Crown", "Ivory Codex", "Starlit Lens", "Ash-Key", "Sable Reliquary", "Heart of the Tidelord"]
SECRETS = ["the vanished regiment", "the false saint", "the poison treaty", "the hidden tax ledger", "the necromancer pact", "the map that should not exist"]
RESOURCES = ["silver", "grain", "black powder", "rare inks", "healing draughts", "prison labor"]
MYSTERIES = ["the singing well", "the red comet", "the locked lighthouse", "the ghost census", "the mirrorgate", "the salt-etched prophecy"]

ASSET_LOCATIONS = ["safehouse", "warehouse", "chapterhouse", "fortified manor", "hidden shrine", "smuggler pier", "watchtower", "vault"]
ASSET_FORCES = ["street toughs", "veteran mercenaries", "zealots", "trained hounds", "masked enforcers", "scouts", "apprentice mages"]
ASSET_RESOURCES = ["coin reserve", "blackmail file", "forbidden tome", "cartographer's archive", "smuggler route map", "coded dispatches"]
ASSET_NPCS = ["spymaster", "champion", "high priest", "fixer", "seneschal", "witch-consultant"]

SCHISM_TYPES = [
    "Ideological split", "Succession crisis", "Resource scarcity", "Heresy / corruption",
    "External manipulation", "Leadership rivalry"
]

PUBLIC_FACES = [
    "respectable civic charity", "legitimate trade association", "temple auxiliary", "town watch partner",
    "harmless scholars' society", "popular mercenary outfit", "dockworker union",
]

HIDDEN_TRUTHS = [
    "funds a smuggling pipeline", "harbors a relic cult", "is blackmailed by a rival faction",
    "answers to an inhuman patron", "conducts experiments on the poor", "has infiltrated the clergy",
]

def _pick(rng: random.Random, items: Sequence[str]) -> str:
    return items[rng.randrange(len(items))]


def generate_goal(rng: random.Random) -> Dict[str, Any]:
    gtype, tmpl = _pick(rng, GOAL_TEMPLATES)
    desc = tmpl.format(
        thing=_pick(rng, THINGS),
        place=_pick(rng, PLACES),
        relic=_pick(rng, RELICS),
        secret=_pick(rng, SECRETS),
        resource=_pick(rng, RESOURCES),
        mystery=_pick(rng, MYSTERIES),
    )
    return {
        "id": str(uuid.uuid4()),
        "type": gtype,
        "description": desc,
        "priority": _pick(rng, ["Low", "Medium", "High", "Obsession"]),
        "visibility": _pick(rng, ["Public", "Rumored", "Secret"]),
        "progress": int(rng.random() * 30),
        "deadline": "",
        "success": "",
        "failure": "",
    }


def generate_asset(rng: random.Random) -> Dict[str, Any]:
    cat = _pick(rng, ["Location", "Forces", "Resource", "NPC", "Influence"])
    if cat == "Location":
        name = f"{_pick(rng, ['The', 'Old', 'Hidden', 'Iron', 'Sable', 'Lantern'])} {_pick(rng, ASSET_LOCATIONS).title()}"
        tags = ["Location"]
    elif cat == "Forces":
        name = f"{_pick(rng, ['A squad of', 'A cadre of', 'Two dozen', 'An elite band of'])} {_pick(rng, ASSET_FORCES)}"
        tags = ["Forces"]
    elif cat == "Resource":
        name = f"{_pick(rng, ['Stash of', 'Reserve of', 'Cache of', 'Supply of'])} {_pick(rng, ASSET_RESOURCES)}"
        tags = ["Resource"]
    elif cat == "NPC":
        name = f"{_pick(rng, ['The', 'A', 'Their'])} {_pick(rng, ASSET_NPCS)}"
        tags = ["NPC"]
    else:
        name = _pick(rng, ["Council favor", "Dockside leverage", "Court access", "Temple protection", "License to operate"])
        tags = ["Influence"]

    return {
        "id": str(uuid.uuid4()),
        "category": cat,
        "name": name,
        "security": _pick(rng, ["Low", "Medium", "High", "Mythic"]),
        "mobility": _pick(rng, ["Fixed", "Mobile", "Hidden"]),
        "known": _pick(rng, ["Known", "Rumored", "Secret"]),
        "tags": tags,
        "notes": "",
    }


def generate_schism(rng: random.Random) -> Dict[str, Any]:
    stype = _pick(rng, SCHISM_TYPES)
    side_a = _pick(rng, ["Purists", "Pragmatists", "Blades", "Cloaks", "Old Guard", "New Blood"])
    side_b = _pick(rng, ["Reformers", "Zealots", "Coin-Men", "Scribes", "Faithful", "Usurpers"])
    a_power = rng.randint(35, 65)
    return {
        "id": str(uuid.uuid4()),
        "type": stype,
        "factions": [
            {"name": side_a, "power": a_power, "agenda": ""},
            {"name": side_b, "power": 100 - a_power, "agenda": ""},
        ],
        "flashpoint": "",
        "clock": rng.randint(0, 3),
        "outcome": "",
        "notes": "",
    }


def generate_timeline_event(rng: random.Random, faction_name: str) -> Dict[str, Any]:
    verb = _pick(rng, ["moves against", "pressures", "bribes", "threatens", "recruits from", "strikes at", "negotiates with"])
    target = _pick(rng, ["the watch", "a rival guild", "a minor noble", "the docks", "a temple", "a caravan", "the undercity"])
    return {
        "id": str(uuid.uuid4()),
        "created": now_iso(),
        "title": f"{faction_name} {verb} {target}",
        "details": "",
        "tags": ["FactionEvent"],
    }


def generate_faction(rng: random.Random, *, name: Optional[str] = None) -> Dict[str, Any]:
    ftype = _pick(rng, FACTION_TYPES)
    ethos = _pick(rng, ETHOS)
    base_name = name or f"{_pick(rng, ['The', 'Order of the', 'House', 'Circle of the', 'Brotherhood of'])} {_pick(rng, ['Sable', 'Lantern', 'Ash', 'Ivory', 'Gloam', 'Cinder', 'Verdant'])} {_pick(rng, ['Hand', 'Covenant', 'Crown', 'League', 'Veil', 'Accord', 'Spiral'])}"
    fid = slugify(base_name) + "_" + str(rng.randint(100, 999))
    faction = {
        "id": fid,
        "name": base_name,
        "type": ftype,
        "ethos": ethos,
        "threat": _pick(rng, ["Local", "Regional", "Major", "Existential"]),
        "tone": _pick(rng, ["Grim", "Political", "Weird", "Heroic", "Bleak"]),
        "public_face": _pick(rng, PUBLIC_FACES),
        "hidden_truth": _pick(rng, HIDDEN_TRUTHS),
        "motto": _pick(rng, ["We endure.", "Nothing is free.", "The old law stands.", "By ink and blood.", "Quietly, always.", "No witnesses."]),
        "tags": [],
        "notes": "",
        "goals": [generate_goal(rng) for _ in range(rng.randint(2, 4))],
        "assets": [generate_asset(rng) for _ in range(rng.randint(2, 5))],
        "relationships": [],
        "schisms": [generate_schism(rng)] if rng.random() < 0.7 else [],
        "timeline": [generate_timeline_event(rng, base_name) for _ in range(rng.randint(1, 3))],
    }
    return faction



REL_TYPES = ["Ally", "Rival", "Enemy", "Subordinate", "Patron", "Unaware"]

def reciprocal_relationship(rel_type: str) -> str:
    rel_type = (rel_type or "").strip()
    if rel_type == "Patron":
        return "Subordinate"
    if rel_type == "Subordinate":
        return "Patron"
    # Ally/Enemy/Rival/Unaware are symmetric for our purposes
    return rel_type or "Rival"


def _ensure_min_list(rng: random.Random, items: List[Any], make_item, min_n: int, max_n: int) -> List[Any]:
    n = max(min_n, min(len(items), max_n))
    while len(items) < n:
        items.append(make_item(rng))
    # If we somehow exceeded max_n, trim deterministically
    if len(items) > max_n:
        items = items[:max_n]
    return items


def generate_faction_full(
    rng: random.Random,
    *,
    name: Optional[str] = None,
    richness: int = 2
) -> Dict[str, Any]:
    """Generate a faction with fuller default population.

    richness: 1 (lighter) .. 3 (heavier)
    """
    richness = max(1, min(3, int(richness or 2)))
    f = generate_faction(rng, name=name)

    # Expand lists based on richness
    if richness == 1:
        goal_min, goal_max = 2, 4
        asset_min, asset_max = 2, 5
        schism_chance = 0.55
        tl_min, tl_max = 1, 3
    elif richness == 2:
        goal_min, goal_max = 3, 6
        asset_min, asset_max = 3, 7
        schism_chance = 0.75
        tl_min, tl_max = 2, 5
    else:
        goal_min, goal_max = 4, 8
        asset_min, asset_max = 4, 9
        schism_chance = 0.85
        tl_min, tl_max = 3, 7

    f["goals"] = _ensure_min_list(rng, list(f.get("goals") or []), generate_goal, goal_min, goal_max)
    f["assets"] = _ensure_min_list(rng, list(f.get("assets") or []), generate_asset, asset_min, asset_max)

    schisms = list(f.get("schisms") or [])
    if not schisms and rng.random() < schism_chance:
        schisms.append(generate_schism(rng))
    # sometimes add a second schism at higher richness
    if richness >= 2 and len(schisms) < 2 and rng.random() < (0.25 * richness):
        schisms.append(generate_schism(rng))
    f["schisms"] = schisms

    tl = list(f.get("timeline") or [])
    while len(tl) < tl_min:
        tl.append(generate_timeline_event(rng, f.get("name","Faction")))
    if len(tl) > tl_max:
        tl = tl[:tl_max]
    f["timeline"] = tl
    return f


def generate_factions_batch(
    rng: random.Random,
    *,
    count: int,
    richness: int = 2
) -> List[Dict[str, Any]]:
    """Generate multiple factions and auto-wire relationships between them."""
    count = max(2, min(30, int(count or 6)))
    richness = max(1, min(3, int(richness or 2)))

    factions: List[Dict[str, Any]] = []
    used_names: set[str] = set()

    # Generate factions
    for _ in range(count):
        # Try to avoid exact duplicate names
        tries = 0
        f = generate_faction_full(rng, richness=richness)
        while f.get("name") in used_names and tries < 5:
            f = generate_faction_full(rng, richness=richness)
            tries += 1
        used_names.add(f.get("name"))
        factions.append(f)

    # Build relationship web
    by_id = {f["id"]: f for f in factions}
    ids = [f["id"] for f in factions]

    # Relationship density based on richness
    if richness == 1:
        rel_min, rel_max = 1, 2
    elif richness == 2:
        rel_min, rel_max = 2, 4
    else:
        rel_min, rel_max = 3, 6

    # Helper to add relationship (and reciprocal)
    def add_pair(a_id: str, b_id: str, rel_type: str, tension: str, history: str) -> None:
        a = by_id[a_id]
        b = by_id[b_id]
        # Prevent duplicates
        def has_rel(src, target):
            for r in src.get("relationships") or []:
                if (r.get("target") or "").strip() == target:
                    return True
            return False

        if not has_rel(a, b.get("name","")):
            a.setdefault("relationships", []).append({
                "id": str(uuid.uuid4()),
                "type": rel_type,
                "target": b.get("name",""),
                "tension": tension,
                "history": history,
            })
        r2 = reciprocal_relationship(rel_type)
        if not has_rel(b, a.get("name","")):
            b.setdefault("relationships", []).append({
                "id": str(uuid.uuid4()),
                "type": r2,
                "target": a.get("name",""),
                "tension": tension,
                "history": history,
            })

    HISTORY_SNIPPETS = [
        "Old debt; neither side admits the full story.",
        "Blood was spilled over a border dispute.",
        "A stolen relic changed hands twice in one night.",
        "They share a secret route no one else knows.",
        "A marriage pact went wrong; knives came out.",
        "Mutual enemies force an uneasy cooperation.",
        "One side believes the other is infiltrated.",
    ]

    # Create a connected backbone first (chain) for coherence
    for i in range(len(ids)-1):
        a_id = ids[i]
        b_id = ids[i+1]
        rel_type = _pick(rng, ["Rival", "Enemy", "Ally"])
        tension = str(rng.randint(2, 9))
        history = _pick(rng, HISTORY_SNIPPETS)
        add_pair(a_id, b_id, rel_type, tension, history)

    # Add extra random edges
    for a_id in ids:
        a = by_id[a_id]
        desired = rng.randint(rel_min, rel_max)
        # Choose targets by id but store by name
        existing_targets = set((r.get("target") or "").strip() for r in (a.get("relationships") or []))
        attempts = 0
        while len(existing_targets) < desired and attempts < 30:
            b_id = _pick(rng, [x for x in ids if x != a_id])
            b = by_id[b_id]
            b_name = (b.get("name") or "").strip()
            if not b_name or b_name in existing_targets:
                attempts += 1
                continue
            rel_type = _pick(rng, REL_TYPES)
            tension = str(rng.randint(1, 10))
            history = _pick(rng, HISTORY_SNIPPETS)
            add_pair(a_id, b_id, rel_type, tension, history)
            existing_targets.add(b_name)
            attempts += 1

    return factions

