# =========================
# campaign_forge/plugins/planargen/generator.py
# =========================
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Tuple, Any
import textwrap


# ----------------------------------------------------------------------------
# Core Data Models
# ----------------------------------------------------------------------------

@dataclass
class PlaneProfile:
    # Identity
    name: str
    native_name: str
    classification: str
    tone: str
    tagline: str

    # Cosmology + Laws
    cosmological_role: str
    physical_laws: List[str]
    metaphysical_laws: List[str]

    # Sensory
    visuals: str
    soundscape: str
    air_texture: str

    # People / Powers
    ruler: str
    denizens: List[str]
    factions: List[str]
    conflicts: List[str]

    # Geography / Regions
    layout: str
    regions: List[str]

    # Travel
    entry_methods: List[str]
    travel_rules: List[str]
    escape_conditions: List[str]

    # Material bleed
    bleed_effects: List[str]
    long_term_consequences: List[str]

    # Hooks
    hooks: List[str]

    # Seeds / provenance
    seed: int
    iteration: int

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ----------------------------------------------------------------------------
# Ad-lib engine
# ----------------------------------------------------------------------------

class Adlib:
    """
    Lightweight ad-lib / templating engine.

    Template tokens:
      {token} -> filled from pools[token]
      [[optA|optB|optC]] -> choose one option (may contain tokens)

    Supports recursive expansion with a depth limit.
    """
    def __init__(self, pools: Dict[str, List[str]]):
        self.pools = pools

    def expand(self, rng, template: str, depth: int = 4) -> str:
        out = template

        # Expand [[a|b|c]] segments
        for _ in range(64):
            start = out.find("[[")
            if start < 0:
                break
            end = out.find("]]", start + 2)
            if end < 0:
                break
            block = out[start + 2:end]
            options = [o.strip() for o in block.split("|") if o.strip()]
            choice = rng.choice(options) if options else ""
            out = out[:start] + choice + out[end + 2:]

        # Expand {tokens}
        # Do a few passes for nested tokens in chosen text.
        for _ in range(depth):
            changed = False
            i = 0
            while i < len(out):
                if out[i] == "{":
                    j = out.find("}", i + 1)
                    if j > i:
                        key = out[i + 1:j].strip()
                        if key in self.pools and self.pools[key]:
                            out = out[:i] + rng.choice(self.pools[key]) + out[j + 1:]
                            changed = True
                            continue
                i += 1
            if not changed:
                break

        # Clean spacing
        out = out.replace("  ", " ").strip()
        return out


# ----------------------------------------------------------------------------
# Content Packs (starter content)
# ----------------------------------------------------------------------------

CLASSIFICATIONS = [
    "Elemental",
    "Conceptual",
    "Afterlife",
    "Artificial",
    "Parasitic",
    "Prison-Seal",
    "Transit",
    "Failed Creation",
    "Divine Domain",
    "Refuge-Exile",
]

TONES = [
    "Mythic",
    "Horror",
    "Surreal",
    "Whimsical",
    "Cosmic",
    "Grim OSR",
]

LAYOUT_STYLES = [
    "Infinite expanse with repeating landmarks",
    "Finite plane with unreachable edges",
    "Layered strata (upper/lower worlds)",
    "Floating regions drifting in void",
    "Rotating zones around a fixed axis",
    "Shifting geography that reorders at dawn",
    "Spiral continent with inward descent",
    "Archipelago of concepts (islands of ideas)",
]

ENTRY_METHODS = [
    "A ritual performed with a {key_object}",
    "Accidental breach during a storm of {strange_weather}",
    "A door that appears only when you {entry_condition}",
    "A dream-path: sleep beneath {dream_anchor}",
    "Death by {death_mode} (only works once)",
    "A machine: the {machine_name} tuned to {frequency}",
    "A map drawn in {ink_type} that becomes a gateway when burned",
]

ESCAPE_CONDITIONS = [
    "Speak your true name to {ruler_title} and be judged",
    "Offer a memory of {memory_subject} to the plane itself",
    "Follow the {guiding_sign} until it repeats three times",
    "Carry {escape_token} across the border without looking back",
    "Complete a bargain with {faction_name}",
    "Die again, but in the opposite manner",
    "Find the exit-structure called {exit_structure}",
]

TRAVEL_RULES = [
    "Distances shrink when you {emotion} and stretch when you {counter_emotion}",
    "Paths re-route unless you carry {navigation_token}",
    "Time advances only when you {time_trigger}",
    "The landscape mirrors the last lie spoken within earshot",
    "You cannot walk in a straight line for more than {steps_limit} steps",
    "Any fire attracts {predator_type} within minutes",
    "You must pay a toll of {toll} at each threshold",
]

BLEED_EFFECTS = [
    "Local weather develops {weird_weather} patterns",
    "Dreams in the region become {dream_effect}",
    "Animals are born with {mutation}",
    "Mirrors show {mirror_truth}",
    "The dead whisper {dead_message}",
    "Maps subtly redraw themselves toward {plane_name_echo}",
]

LONG_TERM_CONSEQUENCES = [
    "The plane begins to remember the party as {party_aspect}",
    "A {faction_name} marks the party for recruitment or removal",
    "A minor law of reality changes: {small_law_change}",
    "A gate becomes stable, attracting {outsider_group}",
    "An artifact from the plane grows in power: {artifact_growth}",
    "The ruler’s attention sharpens: {ruler_attention}",
]

# --- Token pools (base) ---
BASE_POOLS = {
    # Naming / motifs
    "plane_noun": ["Sea", "Throne", "Garden", "Archive", "Chasm", "Court", "Furnace", "Labyrinth", "Mirror", "Choir", "Grave", "Clock"],
    "plane_adj": ["Ashen", "Ivory", "Hollow", "Gilded", "Last", "Crimson", "Silent", "Shattered", "Endless", "Starless", "Kind", "Bitter"],
    "plane_abstract": ["Regret", "Joy", "Rust", "Mercy", "Doubt", "Wonder", "Hunger", "Memory", "Silence", "Echo", "Oath", "Fear"],
    "prefix": ["The", "Saint", "Black", "Old", "New", "First", "Final", "Unseen", "Broken", "Bright"],
    "suffix": ["of Teeth", "of Unmaking", "of Gentle Rain", "of Seven Sorrows", "of Borrowed Light", "of the Unnamed", "of Soft Knives"],

    "ruler_title": ["the Warden", "the Choir-King", "the Pale Regent", "the Clock-Empress", "the Laughing Judge", "the Root-Mind", "the Null Architect"],
    "ruler_style": ["a god", "a dead god’s shadow", "a consensus intelligence", "an ancient machine", "a saint turned tyrant", "a swarm-mind", "a living idea"],

    "key_object": ["a bone key", "a silver nail", "a lantern filled with moths", "a page torn from an angel’s book", "a basalt coin", "a mirror shard"],
    "strange_weather": ["glass rain", "pollen lightning", "black snow", "salt wind", "red fog", "soft thunder"],
    "entry_condition": ["tell a secret aloud", "forgive an enemy", "break a promise", "burn a map", "spill wine on bare stone"],
    "dream_anchor": ["a cairn of names", "a lake that reflects tomorrow", "the roots of an ancient tree", "a ruined altar in moonlight"],
    "death_mode": ["drowning", "poisoning", "freezing", "burning", "falling", "suffocation"],
    "machine_name": ["Axiom Engine", "Halting Gate", "Eidolon Loom", "Vesper Prism", "Mercy Coil", "Sable Aperture"],
    "frequency": ["a lullaby", "a prayer", "a threat", "a mathematical proof", "a confession", "a funeral bell"],
    "ink_type": ["iron gall ink", "squid ink", "blood", "ash-water", "gold leaf", "dream-ink"],

    "memory_subject": ["your childhood home", "a lover’s face", "the taste of summer", "your greatest failure", "your proudest victory"],
    "guiding_sign": ["a flock of paper birds", "a dripping constellation", "a backwards shadow", "a bell that rings without sound"],
    "escape_token": ["a ribbon of dawn", "a shard of lawful stone", "a coin minted with your name", "a thorn that won’t stop bleeding"],
    "exit_structure": ["the Last Door", "the Seam", "the Skin-Gate", "the Quiet Stair", "the Sundering Arch"],
    "faction_name": ["the Cartographers of Sighs", "the Choir of Rivets", "the Ash Monks", "the Candlemakers", "the Red Treaty", "the Pilgrims of Static"],
    "emotion": ["hope", "rage", "love", "fear", "curiosity", "grief"],
    "counter_emotion": ["doubt", "calm", "detachment", "defiance", "apathy", "certainty"],
    "navigation_token": ["a compass that points to guilt", "a breadcrumb of salt", "a ribbon tied to your wrist", "a candle that burns cold"],
    "time_trigger": ["take a vow", "tell the truth", "sleep", "spill blood", "laugh", "forget something important"],
    "steps_limit": ["13", "33", "7", "21", "9", "66"],
    "predator_type": ["moths the size of dogs", "hollow knights", "echo-wolves", "glass eels", "smiling statues"],
    "toll": ["a song", "a year of your life", "a drop of blood", "a promise", "a secret", "your shadow for an hour"],

    "weird_weather": ["impossible tides", "localized gravity gusts", "slow auroras", "whisper-fronts", "sudden eclipse"],
    "dream_effect": ["lucid and prophetic", "violent and contagious", "sweet but draining", "filled with чужие memories", "repeating the same door"],
    "mutation": ["extra eyes", "script-like scars", "feathers of soot", "metallic teeth", "bioluminescent veins"],
    "mirror_truth": ["your last betrayal", "the face you’ll die with", "what you truly want", "a version of you that stayed behind"],
    "dead_message": ["warnings", "confessions", "directions", "prayers", "accusations"],
    "plane_name_echo": ["a distant arch", "a black shoreline", "a tower that wasn’t there yesterday", "a wound in the air"],

    "party_aspect": ["thieves", "pilgrims", "prophets", "contagion", "missing pieces", "unfinished stories"],
    "small_law_change": ["shadows lag behind their owners", "iron tastes like mint", "lies cause nosebleeds", "salt repels fire", "names fade from paper"],
    "outsider_group": ["cultists", "merchants", "refugees", "saints", "hunters", "scholars"],
    "artifact_growth": ["it whispers instructions", "it sprouts veins", "it demands offerings", "it begins to sing", "it attracts storms"],
    "ruler_attention": ["you are watched in reflections", "omens follow you", "your dreams become court sessions", "your footsteps leave sigils"],

    # Descriptive atoms
    "visual_motif": ["floating monoliths", "fractured horizons", "root-bridges", "paper seas", "clockwork reefs", "singing fog"],
    "color": ["copper", "indigo", "bone-white", "verdigris", "blood-red", "ashen grey", "opal"],
    "geometry": ["non-Euclidean angles", "spiral valleys", "impossible staircases", "folded plains", "inside-out cliffs"],
    "sound": ["distant choirs", "insect violin", "soft thunder", "glass chimes", "a heartbeat in the ground", "radio hiss"],
    "air": ["oily", "sharp", "heavy", "cold and sweet", "dry as paper", "warm like breath"],
    "scent": ["ozone", "incense", "wet stone", "burnt sugar", "iron", "mold and flowers"],
}

NAME_TEMPLATES = [
    "{prefix} {plane_adj} {plane_noun}",
    "{prefix} {plane_noun} {suffix}",
    "{prefix} {plane_adj} {plane_abstract}",
    "{plane_adj} {plane_noun} {suffix}",
    "{prefix} {plane_abstract} {suffix}",
]

NATIVE_NAME_TEMPLATES = [
    "Xhûl-{plane_abstract}",
    "Vael-{plane_noun}",
    "Keth {plane_adj}’ath",
    "Oru-{plane_abstract}-{plane_noun}",
    "Ssae’{plane_adj}",
]

TAGLINE_TEMPLATES = [
    "A plane where {metaphys_law_short} and {phys_law_short}.",
    "A {classification} dominion ruled by {ruler_title}, shaped by {theme_noun}.",
    "A place of {tone_adj} wonder: {one_line_hook}.",
]

COSMOLOGICAL_ROLE_TEMPLATES = [
    "This plane exists as [[a filter|a crucible|a quarantine|a sanctuary|a proving ground]] between worlds. It was made to {role_purpose}, but now it {role_twist}.",
    "Scholars say it formed when {origin_event}. The plane’s purpose is {role_purpose}, and every visitor becomes {visitor_fate}.",
    "It was [[built|born|accidentally spilled]] from {origin_source}. Its cosmological role is to {role_purpose}; if it fails, {role_failure}.",
]

PHYSICAL_LAW_TEMPLATES = [
    "Gravity obeys [[belief|music|bloodlines|spoken names|the nearest tower]]; down is not guaranteed.",
    "Time flows [[in loops of {steps_limit} hours|only when you {time_trigger}|in sudden jumps during storms]].",
    "Light comes from [[no sun at all|a ring of {color} moons|the eyes of statues|floating lantern-fish]] and casts shadows that {shadow_behavior}.",
    "Matter is [[brittle as glass|soft as clay|alive with nerves|filled with humming sand]]; objects {object_behavior}.",
]

METAPHYSICAL_LAW_TEMPLATES = [
    "Promises become physical: a vow manifests as [[chains|flowers|ink|rust|a halo]] until fulfilled or broken.",
    "Names have mass. Speak a name too often and it begins to [[sink|echo|bleed|warp the ground]] around you.",
    "Strong emotions rewrite terrain: {emotion} raises {terrain_rise}; {counter_emotion} summons {terrain_fall}.",
    "Lies attract {predator_type}; truth repels them but leaves scars in the air.",
    "Death is negotiable: the dead may return if you pay {toll}, but they come back missing {missing_piece}.",
]

SENSORY_VISUAL_TEMPLATES = [
    "The sky is {color}, crossed by {visual_motif}. The land forms {geometry}, and every horizon feels {tone_adj}.",
    "You see {visual_motif} over {color} plains, where {geometry} repeats like a bad memory.",
]

SENSORY_SOUND_TEMPLATES = [
    "The air carries {sound}. Silence arrives in patches, like [[blank pages|snuffed candles|closed mouths]].",
    "Sound behaves strangely: {sound} comes from behind you even when the source is ahead.",
]

SENSORY_AIR_TEMPLATES = [
    "Breathing feels {air}, and it tastes faintly of {scent}.",
    "The atmosphere is {air}; every inhale suggests {scent} and distant thunder.",
]

RULER_TEMPLATES = [
    "{ruler_title} — {ruler_style} who enforces [[mercy|order|beauty|hunger|silence]] through {enforcement_method}.",
    "{ruler_title}, once [[a saint|a tyrant|a gardener|a judge|a machine]]; now they rule by {enforcement_method}.",
    "No singular ruler: authority is held by {faction_name}, and their law is {law_style}.",
]

DENIZEN_TEMPLATES = [
    "Common denizens include [[{predator_type}|{outsider_group}|pilgrims made of {material}|{creature_form}]] who {denizen_behavior}.",
    "You often encounter {creature_form}, [[stitched|grown|forged]] from {material}; they communicate via {communication}.",
]

FACTION_TEMPLATES = [
    "{faction_name}: They seek {faction_goal}, hoarding {resource} and fearing {fear}.",
    "{faction_name}: They police {rule_topic}, offering bargains in exchange for {toll}.",
]

CONFLICT_TEMPLATES = [
    "A conflict simmers: {faction_name} and {faction_name} feud over {resource}, and the loser will be {stakes}.",
    "The plane is destabilizing: {stability_threat}. If unchecked, it will {collapse_result}.",
    "A prophecy-clock ticks: when {prophecy_trigger} occurs, {prophecy_result}.",
]

REGION_TEMPLATES = [
    "{region_name} — {region_desc}. Danger: {region_danger}. Opportunity: {region_opportunity}.",
    "{region_name}: {region_desc}. It is known for {region_feature} and haunted by {predator_type}.",
]

HOOK_TEMPLATES = [
    "Recover {macguffin} from {region_name} before {prophecy_result}.",
    "Negotiate passage with {faction_name}; they demand {toll} and a promise to {bargain_term}.",
    "Stop {stability_threat} by confronting {ruler_title} in {region_name}.",
    "Escort a {outsider_group} caravan through {region_name} while obeying the law: {metaphys_law_short}.",
    "Steal a secret from {faction_name} that explains why the plane {role_twist}.",
]

# Additional tokens referenced above
EXTRA_POOLS = {
    "theme_noun": ["rust", "oaths", "storms", "mirrors", "thorns", "choirs", "salt", "ash"],
    "tone_adj": ["haunting", "radiant", "unsettling", "dreamlike", "knife-edged", "grim", "tender"],
    "one_line_hook": ["a door that wants your name", "a sea that remembers faces", "a court where lies bleed", "a garden that eats maps"],
    "role_purpose": ["contain {predator_type}", "digest broken oaths", "refine souls into {material}", "store {plane_abstract} like fuel", "protect a sleeping god"],
    "role_twist": ["leaks into nearby worlds", "hungers for visitors", "forgets its own rules", "is being rewritten by outsiders", "slowly collapses inward"],
    "origin_event": ["a god’s death", "a failed apotheosis", "a war between concepts", "a ritual misfire", "a clock stopping"],
    "origin_source": ["a dead star", "the dreams of a titan", "a council of judges", "an engine beneath reality", "a library that burned"],
    "visitor_fate": ["a witness", "a resource", "a suspect", "a seed", "a meal"],
    "role_failure": ["the border between worlds thins", "the dead stop resting", "time stutters in the material plane", "magic tastes like iron for a generation"],
    "shadow_behavior": ["argue with their owners", "arrive late", "refuse to cross thresholds", "whisper names"],
    "object_behavior": ["remember prior owners", "grow warm near lies", "slowly turn to salt", "try to return to where they were made"],
    "terrain_rise": ["spires", "ridges", "thrones", "walls of bone", "towers of paper"],
    "terrain_fall": ["pits", "lakes", "fog seas", "fields of ash", "quiet valleys"],
    "missing_piece": ["a name", "a year", "a finger", "their laughter", "a shadow"],
    "enforcement_method": ["contracts written in skin", "choirs that rewrite thought", "mirrors that judge", "storms that erase footprints"],
    "law_style": ["consensus", "ritual duels", "public confession", "silent ballots cast in blood"],
    "material": ["glass", "salt", "paper", "bone", "clockwork", "fungus", "smoke"],
    "creature_form": ["limbed masks", "lantern-bodied pilgrims", "hollow knights", "reef-serpents", "ink-stained angels"],
    "denizen_behavior": ["trade in {memory_subject}", "hunt {emotion}", "sing warnings", "collect names", "build shrines from teeth"],
    "communication": ["clicks and harmonics", "scent and gesture", "written sigils in the air", "borrowed voices", "small bells"],
    "faction_goal": ["map the unmappable", "end the ruler’s reign", "profit from gates", "protect refugees", "harvest {theme_noun}"],
    "resource": ["gate-keys", "memories", "salt-coins", "names", "time-crumbs", "living maps"],
    "fear": ["the ruler’s gaze", "truth", "outsiders", "stillness", "the sea swallowing their archives"],
    "rule_topic": ["speech", "names", "fire", "dreaming", "trade"],
    "stakes": ["exiled into the void", "turned into a landmark", "made part of the ruler", "rewritten as a law"],
    "stability_threat": ["the seams are tearing", "a second sky is forming", "the plane’s heartbeat is failing", "someone is rewriting the laws"],
    "collapse_result": ["fold into a single point", "spill into the material world", "become a prison for everyone inside", "forget itself entirely"],
    "prophecy_trigger": ["the {exit_structure} opens", "the {guiding_sign} appears", "three lies are spoken at noon", "the last bell rings"],
    "prophecy_result": ["the ruler must abdicate", "a gate becomes permanent", "the sea rises and names drown", "the plane swaps places with a mortal city"],
    "region_name": ["The {plane_adj} Shore", "The {plane_noun} of {plane_abstract}", "The {color} Stair", "The {visual_motif} Fields", "The Quiet Spire"],
    "region_desc": ["a place where {sound} pools", "a labyrinth of {material} corridors", "a basin filled with {strange_weather}", "a court of unmoving statues"],
    "region_danger": ["{predator_type}", "a law: {metaphys_law_short}", "time skipping", "mirrors that accuse"],
    "region_opportunity": ["a cache of {resource}", "an audience with {ruler_title}", "a stable gate", "a bargain with {faction_name}"],
    "region_feature": ["singing stones", "salt rivers", "paper forests", "clockwork reefs", "ash gardens"],
    "macguffin": ["the {key_object}", "a contract of {plane_abstract}", "the heart-gear of the plane", "a map that leads out", "a crown of {material}"],
    "bargain_term": ["carry a message to {origin_source}", "destroy a mirror in {region_name}", "bring back {memory_subject}", "name a newborn denizen"],
    # Short law tokens used in tagline/hook summaries
    "metaphys_law_short": ["promises become physical", "names weigh you down", "emotions reshape the land", "lies attract predators", "death requires bargaining"],
    "phys_law_short": ["gravity obeys belief", "time advances on triggers", "light comes from lantern-fish", "matter remembers owners", "shadows refuse thresholds"],
}

# Merge pools
def build_pools(classification: str, tone: str, plane_name_echo: Optional[str] = None) -> Dict[str, List[str]]:
    pools = {}
    pools.update(BASE_POOLS)
    pools.update(EXTRA_POOLS)

    # Subtle biasing by classification and tone: inject a few curated options
    if classification == "Elemental":
        pools["theme_noun"] += ["flame", "ice", "storm", "stone", "acid", "ember"]
        pools["material"] += ["obsidian", "coral", "ice"]
    elif classification == "Afterlife":
        pools["theme_noun"] += ["judgment", "rest", "penance", "memory"]
        pools["ruler_title"] += ["the Ferryman", "the Archivist of Ash", "the Lantern Saint"]
        pools["metaphys_law_short"] += ["the dead can bargain", "regret becomes terrain"]
    elif classification == "Prison-Seal":
        pools["theme_noun"] += ["chains", "locks", "silence", "containment"]
        pools["exit_structure"] += ["the Sevenfold Lock", "the Black Latch"]
        pools["role_purpose"] += ["hold the {predator_type} forever", "seal a {plane_abstract} catastrophe"]
    elif classification == "Transit":
        pools["theme_noun"] += ["roads", "doors", "seams", "maps"]
        pools["navigation_token"] += ["a passport of bone", "a toll-stamp on your tongue"]
    elif classification == "Failed Creation":
        pools["theme_noun"] += ["errors", "cracks", "unfinished math"]
        pools["origin_event"] += ["a god’s typo", "a broken theorem", "a half-spoken wish"]
    elif classification == "Artificial":
        pools["theme_noun"] += ["gears", "protocols", "laws", "wheels"]
        pools["ruler_style"] += ["a supervisory program", "a planner-mind"]
    elif classification == "Divine Domain":
        pools["theme_noun"] += ["ritual", "worship", "revelation"]
        pools["ruler_style"] += ["a jealous god", "a patron saint", "a masked divinity"]

    if tone == "Horror":
        pools["tone_adj"] = ["haunting", "rotting", "dread-soaked", "claustrophobic", "hungry"]
        pools["predator_type"] += ["skin-kites", "bone lanterns", "smile-worms"]
    elif tone == "Whimsical":
        pools["tone_adj"] = ["playful", "storybook", "oddly kind", "silly-dangerous", "charming"]
        pools["predator_type"] += ["argument-bees", "hat-snatching winds", "polite wolves"]
    elif tone == "Cosmic":
        pools["tone_adj"] = ["vast", "indifferent", "star-cold", "unfathomable", "mathematical"]
        pools["origin_source"] += ["a cosmic equation", "the space between axioms"]
    elif tone == "Grim OSR":
        pools["tone_adj"] = ["grim", "knife-edged", "muddy", "candlelit", "merciless"]
        pools["toll"] += ["rations", "a useful tool", "a torch that won’t relight"]

    # Optional: allow caller to seed a token with the plane's name for bleed-effects
    if plane_name_echo:
        pools["plane_name_echo"] = [plane_name_echo]

    return pools


# ----------------------------------------------------------------------------
# Generation functions
# ----------------------------------------------------------------------------

def _pick_many(rng, items: List[str], n: int) -> List[str]:
    if n <= 0:
        return []
    if not items:
        return []
    if n >= len(items):
        # deterministic shuffle copy
        items2 = list(items)
        rng.shuffle(items2)
        return items2
    items2 = list(items)
    rng.shuffle(items2)
    return items2[:n]


def generate_plane(
    rng,
    seed: int,
    iteration: int,
    classification: str,
    tone: str,
    locks: Optional[Dict[str, Any]] = None,
    depth: str = "Standard",  # "Sketch" | "Standard" | "Deep"
) -> PlaneProfile:
    locks = locks or {}
    pools = build_pools(classification, tone)

    ad = Adlib(pools)

    # Identity
    name = locks.get("name") or ad.expand(rng, rng.choice(NAME_TEMPLATES))
    native_name = locks.get("native_name") or ad.expand(rng, rng.choice(NATIVE_NAME_TEMPLATES))
    # Rebuild pools with plane name echo for bleed effects
    pools = build_pools(classification, tone, plane_name_echo=name)
    ad = Adlib(pools)

    tagline = ad.expand(rng, rng.choice(TAGLINE_TEMPLATES).replace("{classification}", classification))

    # Cosmology + Laws
    cosmological_role = ad.expand(rng, rng.choice(COSMOLOGICAL_ROLE_TEMPLATES))
    physical_laws = [ad.expand(rng, t) for t in _pick_many(rng, PHYSICAL_LAW_TEMPLATES, 3 if depth != "Sketch" else 2)]
    metaphysical_laws = [ad.expand(rng, t) for t in _pick_many(rng, METAPHYSICAL_LAW_TEMPLATES, 3 if depth == "Deep" else 2)]

    # Sensory
    visuals = ad.expand(rng, rng.choice(SENSORY_VISUAL_TEMPLATES))
    soundscape = ad.expand(rng, rng.choice(SENSORY_SOUND_TEMPLATES))
    air_texture = ad.expand(rng, rng.choice(SENSORY_AIR_TEMPLATES))

    # Powers & ecology
    ruler = ad.expand(rng, rng.choice(RULER_TEMPLATES))
    denizens = [ad.expand(rng, t) for t in _pick_many(rng, DENIZEN_TEMPLATES, 2 if depth != "Deep" else 3)]
    factions = [ad.expand(rng, t) for t in _pick_many(rng, FACTION_TEMPLATES, 2 if depth == "Sketch" else 3)]
    conflicts = [ad.expand(rng, t) for t in _pick_many(rng, CONFLICT_TEMPLATES, 2 if depth != "Deep" else 3)]

    # Geography
    layout = locks.get("layout") or rng.choice(LAYOUT_STYLES)
    regions = [ad.expand(rng, t) for t in _pick_many(rng, REGION_TEMPLATES, 3 if depth == "Sketch" else (5 if depth == "Deep" else 4))]

    # Travel
    entry_methods = [ad.expand(rng, t) for t in _pick_many(rng, ENTRY_METHODS, 2 if depth == "Sketch" else 3)]
    travel_rules = [ad.expand(rng, t) for t in _pick_many(rng, TRAVEL_RULES, 2 if depth == "Sketch" else 3)]
    escape_conditions = [ad.expand(rng, t) for t in _pick_many(rng, ESCAPE_CONDITIONS, 2 if depth == "Sketch" else 3)]

    # Bleed
    bleed_effects = [ad.expand(rng, t) for t in _pick_many(rng, BLEED_EFFECTS, 2 if depth == "Sketch" else 3)]
    long_term_consequences = [ad.expand(rng, t) for t in _pick_many(rng, LONG_TERM_CONSEQUENCES, 2 if depth != "Deep" else 3)]

    # Hooks
    hooks = [ad.expand(rng, t) for t in _pick_many(rng, HOOK_TEMPLATES, 5 if depth != "Sketch" else 4)]

    return PlaneProfile(
        name=name,
        native_name=native_name,
        classification=classification,
        tone=tone,
        tagline=tagline,

        cosmological_role=cosmological_role,
        physical_laws=physical_laws,
        metaphysical_laws=metaphysical_laws,

        visuals=visuals,
        soundscape=soundscape,
        air_texture=air_texture,

        ruler=ruler,
        denizens=denizens,
        factions=factions,
        conflicts=conflicts,

        layout=layout,
        regions=regions,

        entry_methods=entry_methods,
        travel_rules=travel_rules,
        escape_conditions=escape_conditions,

        bleed_effects=bleed_effects,
        long_term_consequences=long_term_consequences,

        hooks=hooks,

        seed=seed,
        iteration=iteration,
    )


# ----------------------------------------------------------------------------
# Formatting helpers
# ----------------------------------------------------------------------------

def plane_to_markdown(p: PlaneProfile) -> str:
    def bullets(items: List[str]) -> str:
        return "\n".join([f"- {i}" for i in items]) if items else "- (none)"

    md = f"""\
# {p.name}
*Native Name:* **{p.native_name}**  
*Classification:* **{p.classification}** • *Tone:* **{p.tone}**  
*Seed:* `{p.seed}` • *Iteration:* `{p.iteration}`

> {p.tagline}

---

## Cosmological Role
{p.cosmological_role}

## Fundamental Laws

### Physical
{bullets(p.physical_laws)}

### Metaphysical
{bullets(p.metaphysical_laws)}

---

## Sensory Profile
- **Visuals:** {p.visuals}
- **Sound:** {p.soundscape}
- **Air:** {p.air_texture}

---

## Powers & Inhabitants
- **Authority / Ruler:** {p.ruler}

### Common Denizens
{bullets(p.denizens)}

### Factions
{bullets(p.factions)}

### Conflicts
{bullets(p.conflicts)}

---

## Geography
- **Layout:** {p.layout}

### Key Regions
{bullets(p.regions)}

---

## Travel
### Entry Methods
{bullets(p.entry_methods)}

### Movement Rules
{bullets(p.travel_rules)}

### Escape Conditions
{bullets(p.escape_conditions)}

---

## Bleed-Through to the Material World
### Immediate Effects
{bullets(p.bleed_effects)}

### Long-Term Consequences
{bullets(p.long_term_consequences)}

---

## Adventure Hooks
{bullets(p.hooks)}
"""
    return textwrap.dedent(md).strip() + "\n"
