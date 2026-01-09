from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Tuple
import math


# -----------------------------
# Data model
# -----------------------------

@dataclass
class Relationship:
    a: str
    b: str
    rel_type: str           # Ally, Rival, Parent, Child, Lover, Betrayer, Oathbound, Usurper, Usurped, Enemy, Dependent, Patron, Ward
    intensity: int          # 1-5
    status: str             # Stable, Strained, Cold War, Open Conflict, Secret
    secret: str             # hidden truth or twist
    directional: bool = False
    a_to_b_note: str = ""
    b_to_a_note: str = ""


@dataclass
class God:
    gid: str
    name: str
    titles: List[str]
    epithet: str
    tier: str               # Greater, Lesser, Demigod
    domains_primary: List[str]
    domains_secondary: List[str]
    forbidden: List[str]
    temperament: str
    desire: str
    flaw: str
    taboo: str
    icon_symbol: str
    icon_animal: str
    icon_material: str
    holy_day: str
    worship_style: str
    offerings: List[str]
    clergy: str
    virtues: List[str]
    vices: List[str]
    origin_myth: str
    victory: str
    failure: str
    sin: str
    mortal_belief: str


@dataclass
class Conflict:
    cid: str
    title: str
    gods_involved: List[str]
    cause: str
    stakes: str
    escalation: str
    stability_impact: int   # 1-5


@dataclass
class Pantheon:
    version: int
    name: str
    tone: str
    involvement: str
    structure: str
    seed: int
    iteration: int
    gods: List[God]
    relationships: List[Relationship]
    conflicts: List[Conflict]
    metrics: Dict[str, int]


# -----------------------------
# Starter content tables
# -----------------------------

DEFAULT_TABLES = {
    "tones": [
        "Animist and local", "Classical high myth", "Dark and gnostic", "Cosmic and alien",
        "Baroque and decadent", "Trickster-heavy", "Fading gods", "War of heaven"
    ],
    "involvement": ["Remote", "Intervening", "Warring", "Dying/Fading", "Bound/Imprisoned"],
    "structures": [
        "Family Tree", "Elemental Balance", "Domain Monopoly", "Overlapping Domains",
        "Broken Pantheon", "Imperial Court", "Mask-and-Names (syncretic)"
    ],
    "tiers": ["Greater", "Lesser", "Demigod"],
    "temperaments": [
        "Wrathful", "Indifferent", "Jealous", "Benevolent", "Curious", "Paranoid",
        "Playful", "Severe", "Merciful", "Aloof", "Vindictive", "Hungry"
    ],
    "desires": [
        "Expand worship into new lands",
        "Erase a rival’s name from memory",
        "Restore a lost artifact",
        "Break a binding oath",
        "Elevate a mortal champion",
        "Collapse a dynasty",
        "End an age of magic",
        "Begin an age of storms",
        "Collect a thousand secrets",
        "Purify a corrupted holy site",
        "Reclaim a stolen domain",
        "Prove their supremacy in a public miracle",
    ],
    "flaws": [
        "Pride", "Fear", "Obsession", "Dependency", "Spite", "Cruel curiosity",
        "Cowardice", "Vanity", "Impatience", "Addiction to worship", "Rage", "Envy"
    ],
    "taboos": [
        "Cannot speak lies", "Cannot enter running water", "Cannot refuse a challenge",
        "Cannot harm children", "Cannot break hospitality", "Cannot tolerate iron",
        "Cannot see their own reflection", "Cannot act on holy days", "Cannot kill directly",
        "Cannot cross consecrated salt", "Cannot forgive a betrayal", "Cannot be named aloud"
    ],
    "symbols": [
        "a broken crown", "a thorned halo", "a keyhole sun", "a split mask", "an eye in a cup",
        "three interlocked nails", "a drowned bell", "a ladder of bones", "a spiral brand",
        "a moth-wing sigil", "a meteor rune", "a stitched mouth"
    ],
    "animals": [
        "stag", "serpent", "owl", "wolf", "moth", "eel", "crow", "bull", "spider",
        "horse", "lion", "goat", "shark", "mantis"
    ],
    "materials": [
        "obsidian", "gold leaf", "bone", "salt", "amber", "iron-free silver", "glass",
        "black wax", "moonstone", "ash", "copper", "jade"
    ],
    "holy_days": [
        "the new moon", "the first thunder of spring", "the longest night",
        "the harvest cut", "the day of two shadows", "the storm tide",
        "the first snowfall", "the eclipse hour", "the saint’s procession", "the red dawn"
    ],
    "worship_styles": [
        "State religion", "Secret cult", "Rural folk worship", "Monastic order",
        "Warrior fraternities", "Merchant guild patron", "Oracle circles", "Funerary priesthood"
    ],
    "offerings": [
        "incense and prayers", "bloodletting vow", "coins thrown into water", "a locked secret",
        "bread and salt", "burnt hair", "first fruits", "a vow of silence",
        "a crafted idol", "an animal’s release", "a public confession", "a stolen trophy"
    ],
    "clergy": [
        "masked hierophants", "wandering mendicants", "scribe-priests", "scarred war-clerics",
        "choir of oracles", "undertakers in black", "salt-keepers", "guild-chaplains"
    ],
    "virtues": [
        "Mercy", "Courage", "Hospitality", "Honesty", "Discipline", "Sacrifice",
        "Curiosity", "Patience", "Justice", "Restraint"
    ],
    "vices": [
        "Cruelty", "Greed", "Cowardice", "Pride", "Lust for power", "Deceit",
        "Wrath", "Sloth", "Envy", "Gluttony"
    ],
    "domains": [
        "Storms", "Death", "War", "Secrets", "Fertility", "Hearth", "Travel", "Fate",
        "Hunting", "Sea", "Fire", "Knowledge", "Craft", "Disease", "Justice",
        "Dreams", "Trickery", "Wealth", "Underground", "Beasts", "Stars",
        "Ruin", "Oaths", "Time", "Rebirth", "Music", "Shadows", "Dawn"
    ],
    "epithet_patterns": [
        "the {NOUN} of {NOUN}", "the {ADJ} {NOUN}", "the {NOUN}-Bearer", "the {ADJ} One",
        "the {NOUN} in {NOUN}", "the {ADJ} Flame", "the {NOUN} of Broken {NOUN}",
        "the {ADJ} Judge", "the {NOUN} Who {VERB}s"
    ],
    "adjectives": [
        "Fallow", "Ashen", "Luminous", "Unforgiving", "Hollow", "Crimson", "Sable", "Ivory",
        "Wandering", "Sealed", "Thorned", "Drowned", "Silent", "Burning", "Gilded", "Crooked"
    ],
    "nouns": [
        "Crown", "Gate", "Lantern", "Knife", "Book", "Bell", "Thread", "Cinder", "Mask",
        "Well", "Mirror", "Key", "Spire", "Chain", "Seed", "Oath", "River", "Stone", "Choir"
    ],
    "verbs": [
        "Hears", "Devours", "Judges", "Hides", "Breaks", "Returns", "Wanders",
        "Weighs", "Unmasks", "Sews", "Binds", "Burns"
    ],
    "relationship_types": [
        "Ally", "Rival", "Parent/Child", "Lover", "Betrayer", "Oathbound",
        "Usurper/Usurped", "Ancient Enemy", "Mutual Dependency", "Patron/Ward"
    ],
    "relationship_status": ["Stable", "Strained", "Cold War", "Open Conflict", "Secret"],
    "relationship_secrets": [
        "They share a hidden domain neither admits.",
        "One holds the other’s true name in a sealed reliquary.",
        "Their conflict is staged to distract from a third power.",
        "They are the same god under different masks.",
        "A mortal bloodline binds them to a prophecy.",
        "They traded vows; the receipt is a curse.",
        "They cannot kill one another, only weaken.",
        "They once loved; now they only bargain."
    ],
    "conflict_causes": [
        "Domain overlap sparks unavoidable rivalry.",
        "A sacred artifact was stolen during a holy night.",
        "A mortal empire chose the wrong patron.",
        "An ancient oath was broken publicly.",
        "A dead god’s remains are being harvested.",
        "A prophecy surfaced that names a successor.",
        "A cult committed an atrocity in a god’s name.",
        "A new star appeared—claimed by two thrones."
    ],
    "conflict_stakes": [
        "Control of a key region’s worship and miracles.",
        "Who may judge the dead this century.",
        "Whether a plague becomes a cleansing or a weapon.",
        "Ownership of a newly discovered holy site.",
        "The fate of a royal bloodline bound to the gods.",
        "The stability of the pantheon itself.",
        "Whether magic fades or surges.",
        "Which god may speak on holy days."
    ],
    "conflict_escalations": [
        "Proxy war through cults and knight-orders.",
        "Signs and omens intensify; miracles become dangerous.",
        "A divine avatar walks the world, demanding proof.",
        "Temples burn; relics are unsealed.",
        "A god attempts usurpation through mortal coronation.",
        "A shared domain fractures into two incompatible truths.",
        "A dead god stirs; everyone panics."
    ],
}


# -----------------------------
# Helpers
# -----------------------------

def _slug(s: str) -> str:
    out = []
    for ch in s.lower():
        if ch.isalnum():
            out.append(ch)
        elif ch in (" ", "-", "_"):
            out.append("-")
    slug = "".join(out).strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug[:48] if slug else "pantheon"


def choice(rng, items: List[str]) -> str:
    return items[rng.randrange(0, len(items))]


def sample_unique(rng, items: List[str], k: int) -> List[str]:
    if k <= 0:
        return []
    k = min(k, len(items))
    pool = list(items)
    rng.shuffle(pool)
    return pool[:k]


def clamp_int(x: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, x))


def weighted_tier(rng, mode: str) -> str:
    # power curve mode: flat, tiered
    if mode == "tiered":
        # More lesser than greater
        roll = rng.random()
        if roll < 0.20:
            return "Greater"
        if roll < 0.80:
            return "Lesser"
        return "Demigod"
    return choice(rng, DEFAULT_TABLES["tiers"])


def build_epithet(rng) -> str:
    pat = choice(rng, DEFAULT_TABLES["epithet_patterns"])
    def rep(token: str) -> str:
        if token == "{ADJ}":
            return choice(rng, DEFAULT_TABLES["adjectives"])
        if token == "{NOUN}":
            return choice(rng, DEFAULT_TABLES["nouns"])
        if token == "{VERB}":
            return choice(rng, DEFAULT_TABLES["verbs"])
        return token
    out = pat
    for tok in ["{ADJ}", "{NOUN}", "{VERB}"]:
        while tok in out:
            out = out.replace(tok, rep(tok), 1)
    return out


def domain_pick(rng, all_domains: List[str], primary_count: int, secondary_count: int) -> Tuple[List[str], List[str]]:
    primary = sample_unique(rng, all_domains, primary_count)
    remaining = [d for d in all_domains if d not in primary]
    secondary = sample_unique(rng, remaining, secondary_count)
    return primary, secondary


def pick_forbidden(rng, all_domains: List[str], taken: List[str], k: int) -> List[str]:
    pool = [d for d in all_domains if d not in taken]
    return sample_unique(rng, pool, k)


def make_god_id(name: str, idx: int) -> str:
    return f"g{idx:02d}_{_slug(name)}"


# -----------------------------
# Main generation
# -----------------------------

def generate_pantheon(
    rng,
    pantheon_name: str,
    count: int,
    tone: str,
    involvement: str,
    structure: str,
    power_curve: str,
    name_style: str,
    custom_names: Optional[List[str]] = None
) -> Pantheon:
    # Determine domain overlap behavior
    overlap_heavy = structure in ("Overlapping Domains", "Broken Pantheon", "Mask-and-Names (syncretic)")
    domain_primary_n = 1 if not overlap_heavy else 1
    domain_secondary_n = 1 if not overlap_heavy else 2

    # build names
    names = []
    if custom_names:
        for n in custom_names:
            nn = n.strip()
            if nn:
                names.append(nn)
    # Fill remaining with procedural
    while len(names) < count:
        # Name style: "Epithet-like", "Classical", "Harsh"
        # Keep it simple, make pronounceable-ish
        a = choice(rng, ["A", "E", "I", "O", "U", "Y"])
        cons = choice(rng, ["k", "m", "n", "r", "th", "v", "s", "l", "d", "z", "h", "br", "kr", "sh", "t"])
        mid = choice(rng, ["a", "e", "i", "o", "u", "ae", "ia", "ou"])
        end = choice(rng, ["n", "r", "s", "th", "m", "x", "l", "d", "k"])
        base = (a + cons + mid + end).capitalize()

        if name_style == "Classical":
            suffix = choice(rng, ["os", "a", "on", "eus", "ia", "es", "is"])
            nm = (base + suffix).replace("Y", "I")
        elif name_style == "Harsh":
            nm = (cons + mid + choice(rng, ["k", "g", "z", "th", "rk", "sh"]) + end).capitalize()
        else:
            nm = base

        if nm not in names:
            names.append(nm)

    # Build gods
    gods: List[God] = []
    domains_all = list(DEFAULT_TABLES["domains"])
    for i in range(count):
        nm = names[i]
        tier = weighted_tier(rng, power_curve)

        primary, secondary = domain_pick(rng, domains_all, domain_primary_n, domain_secondary_n)

        # Encourage overlap by occasionally replacing a domain with one already used
        if overlap_heavy and i > 0 and rng.random() < 0.65:
            used = []
            for g in gods:
                used.extend(g.domains_primary)
                used.extend(g.domains_secondary)
            used = [d for d in used if d in domains_all]
            if used:
                if rng.random() < 0.60:
                    primary = [choice(rng, used)]
                # sometimes add a contested secondary
                if rng.random() < 0.50 and secondary:
                    secondary[-1] = choice(rng, used)

        taken = list(primary) + list(secondary)
        forbidden = pick_forbidden(rng, domains_all, taken, k=1 if rng.random() < 0.7 else 2)

        epithet = build_epithet(rng)
        titles = sample_unique(rng, [
            epithet,
            build_epithet(rng),
            build_epithet(rng),
            f"Lord of {choice(rng, DEFAULT_TABLES['nouns'])}",
            f"Lady of {choice(rng, DEFAULT_TABLES['nouns'])}",
        ], k=2)

        temperament = choice(rng, DEFAULT_TABLES["temperaments"])
        desire = choice(rng, DEFAULT_TABLES["desires"])
        flaw = choice(rng, DEFAULT_TABLES["flaws"])
        taboo = choice(rng, DEFAULT_TABLES["taboos"])

        icon_symbol = choice(rng, DEFAULT_TABLES["symbols"])
        icon_animal = choice(rng, DEFAULT_TABLES["animals"])
        icon_material = choice(rng, DEFAULT_TABLES["materials"])
        holy_day = choice(rng, DEFAULT_TABLES["holy_days"])

        worship_style = choice(rng, DEFAULT_TABLES["worship_styles"])
        offerings = sample_unique(rng, DEFAULT_TABLES["offerings"], k=2)
        clergy = choice(rng, DEFAULT_TABLES["clergy"])

        virtues = sample_unique(rng, DEFAULT_TABLES["virtues"], k=2)
        vices = sample_unique(rng, DEFAULT_TABLES["vices"], k=2)

        # Myth snippets
        origin_myth = f"They emerged when {choice(rng, DEFAULT_TABLES['nouns'])} first met {choice(rng, DEFAULT_TABLES['nouns'])}, and the world blinked."
        victory = f"They once {choice(rng, DEFAULT_TABLES['verbs']).lower()} the {choice(rng, DEFAULT_TABLES['adjectives']).lower()} {choice(rng, DEFAULT_TABLES['nouns']).lower()} and claimed its prayers."
        failure = f"They failed to protect a city during {choice(rng, DEFAULT_TABLES['holy_days'])}, and the survivors still spit their name."
        sin = f"They demanded {choice(rng, DEFAULT_TABLES['offerings'])} from an innocent and called it 'balance'."
        mortal_belief = f"Mortals say {nm} {choice(rng, DEFAULT_TABLES['verbs']).lower()} every oath whispered into {choice(rng, DEFAULT_TABLES['nouns']).lower()}."

        gid = make_god_id(nm, i + 1)

        gods.append(God(
            gid=gid,
            name=nm,
            titles=titles,
            epithet=epithet,
            tier=tier,
            domains_primary=primary,
            domains_secondary=secondary,
            forbidden=forbidden,
            temperament=temperament,
            desire=desire,
            flaw=flaw,
            taboo=taboo,
            icon_symbol=icon_symbol,
            icon_animal=icon_animal,
            icon_material=icon_material,
            holy_day=holy_day,
            worship_style=worship_style,
            offerings=offerings,
            clergy=clergy,
            virtues=virtues,
            vices=vices,
            origin_myth=origin_myth,
            victory=victory,
            failure=failure,
            sin=sin,
            mortal_belief=mortal_belief,
        ))

    # Relationships
    relationships: List[Relationship] = []
    # pick edges: roughly N * 1.5 with min to keep graph connected-ish
    edge_target = max(count - 1, int(math.ceil(count * 1.5)))
    pairs = [(i, j) for i in range(count) for j in range(i + 1, count)]
    rng.shuffle(pairs)

    def mk_edge(a: God, b: God) -> Relationship:
        t = choice(rng, DEFAULT_TABLES["relationship_types"])
        intensity = clamp_int(int(rng.random() * 5) + 1, 1, 5)
        status = choice(rng, DEFAULT_TABLES["relationship_status"])
        secret = choice(rng, DEFAULT_TABLES["relationship_secrets"])

        # interpret type with direction when needed
        directional = False
        rel_type = t
        a_note = ""
        b_note = ""

        if t == "Parent/Child":
            directional = True
            if rng.random() < 0.5:
                rel_type = "Parent"
                a_note = f"{a.name} claims to have birthed {b.name} during {a.holy_day}."
                b_note = f"{b.name} resents being treated as an extension of {a.name}."
            else:
                rel_type = "Child"
                a_note = f"{a.name} is said to be the offspring of {b.name}, but denies it."
                b_note = f"{b.name} calls {a.name} 'my wayward spark'."
        elif t == "Usurper/Usurped":
            directional = True
            if rng.random() < 0.5:
                rel_type = "Usurper"
                a_note = f"{a.name} stole a prayer-right once held by {b.name}."
                b_note = f"{b.name} swore a quiet doom upon {a.name}."
            else:
                rel_type = "Usurped"
                a_note = f"{a.name} was stripped of a domain by {b.name}."
                b_note = f"{b.name} keeps the stolen name under {b.icon_material}."
        elif t == "Patron/Ward":
            directional = True
            if rng.random() < 0.5:
                rel_type = "Patron"
                a_note = f"{a.name} shelters {b.name}'s cult in exchange for secret rites."
                b_note = f"{b.name} owes miracles to {a.name}, and hates the debt."
            else:
                rel_type = "Ward"
                a_note = f"{a.name}'s followers hide behind {b.name}'s greater temples."
                b_note = f"{b.name} protects {a.name}… for now."
        elif t == "Betrayer":
            directional = True
            # A betrayed B
            rel_type = "Betrayer"
            a_note = f"{a.name} broke an oath to {b.name} and still bears the mark."
            b_note = f"{b.name} will never forgive; only bargain."

        return Relationship(
            a=a.gid,
            b=b.gid,
            rel_type=rel_type,
            intensity=intensity,
            status=status,
            secret=secret,
            directional=directional,
            a_to_b_note=a_note,
            b_to_a_note=b_note,
        )

    # Ensure connectivity: connect in a chain first
    chain = list(range(count))
    rng.shuffle(chain)
    for idx in range(count - 1):
        a = gods[chain[idx]]
        b = gods[chain[idx + 1]]
        relationships.append(mk_edge(a, b))

    # Add more edges
    for (i, j) in pairs:
        if len(relationships) >= edge_target:
            break
        # Skip if already connected
        ai, bj = gods[i].gid, gods[j].gid
        exists = any((r.a == ai and r.b == bj) or (r.a == bj and r.b == ai) for r in relationships)
        if exists:
            continue
        # Higher chance to relate if domain overlaps
        overlap = len(set(gods[i].domains_primary + gods[i].domains_secondary) & set(gods[j].domains_primary + gods[j].domains_secondary))
        p = 0.35 + 0.20 * overlap
        if rng.random() < min(0.90, p):
            relationships.append(mk_edge(gods[i], gods[j]))

    # Conflicts
    conflicts: List[Conflict] = []
    # conflict target: 1 per ~4 gods, minimum 1
    conflict_target = max(1, count // 4)

    # Score potential conflicts by overlap + relationship intensity
    god_by_id = {g.gid: g for g in gods}

    def overlap_score(g1: God, g2: God) -> int:
        s1 = set(g1.domains_primary + g1.domains_secondary)
        s2 = set(g2.domains_primary + g2.domains_secondary)
        return len(s1 & s2)

    rel_map = {}
    for r in relationships:
        key = tuple(sorted([r.a, r.b]))
        rel_map[key] = r

    pair_scores = []
    for i in range(count):
        for j in range(i + 1, count):
            g1, g2 = gods[i], gods[j]
            ov = overlap_score(g1, g2)
            rel = rel_map.get(tuple(sorted([g1.gid, g2.gid])))
            inten = rel.intensity if rel else 0
            # Rival-ish types more likely
            bias = 0
            if rel and rel.rel_type in ("Rival", "Ancient Enemy", "Usurper", "Usurped", "Betrayer"):
                bias += 2
            score = ov * 2 + inten + bias
            pair_scores.append((score, g1.gid, g2.gid))

    pair_scores.sort(reverse=True, key=lambda x: x[0])

    used_pairs = set()
    for k in range(conflict_target):
        # pick best unused
        pick = None
        for score, a_id, b_id in pair_scores:
            if (a_id, b_id) not in used_pairs and (b_id, a_id) not in used_pairs:
                pick = (score, a_id, b_id)
                break
        if not pick:
            break
        _, a_id, b_id = pick
        used_pairs.add((a_id, b_id))

        g1 = god_by_id[a_id]
        g2 = god_by_id[b_id]
        cause = choice(rng, DEFAULT_TABLES["conflict_causes"])
        stakes = choice(rng, DEFAULT_TABLES["conflict_stakes"])
        escalation = choice(rng, DEFAULT_TABLES["conflict_escalations"])
        stability_impact = clamp_int(2 + overlap_score(g1, g2), 1, 5)

        title = f"{g1.name} vs {g2.name}: {choice(rng, ['The Contested Rite', 'The Broken Oath', 'The Stolen Relic', 'The Two Thrones', 'The Unmasking'])}"
        cid = f"c{k+1:02d}_{_slug(g1.name)}_{_slug(g2.name)}"

        conflicts.append(Conflict(
            cid=cid,
            title=title,
            gods_involved=[a_id, b_id],
            cause=cause,
            stakes=stakes,
            escalation=escalation,
            stability_impact=stability_impact,
        ))

    # Metrics
    # stability starts at 100 and reduced by conflicts intensity and "warring" involvement
    stability = 100
    stability -= sum(c.stability_impact * 6 for c in conflicts)
    if involvement == "Warring":
        stability -= 12
    if involvement == "Dying/Fading":
        stability -= 8
    stability = clamp_int(stability, 0, 100)

    # domain contention: count duplicated domains among gods
    domain_counts = {}
    for g in gods:
        for d in g.domains_primary + g.domains_secondary:
            domain_counts[d] = domain_counts.get(d, 0) + 1
    contention = sum(1 for d, c in domain_counts.items() if c >= 2)

    metrics = {
        "stability": stability,
        "conflicts": len(conflicts),
        "relationships": len(relationships),
        "contested_domains": contention,
    }

    return Pantheon(
        version=1,
        name=pantheon_name,
        tone=tone,
        involvement=involvement,
        structure=structure,
        seed=0,       # caller fills
        iteration=0,  # caller fills
        gods=gods,
        relationships=relationships,
        conflicts=conflicts,
        metrics=metrics,
    )


def pantheon_to_dict(p: Pantheon) -> dict:
    return {
        "version": p.version,
        "name": p.name,
        "tone": p.tone,
        "involvement": p.involvement,
        "structure": p.structure,
        "seed": p.seed,
        "iteration": p.iteration,
        "metrics": dict(p.metrics),
        "gods": [asdict(g) for g in p.gods],
        "relationships": [asdict(r) for r in p.relationships],
        "conflicts": [asdict(c) for c in p.conflicts],
    }
