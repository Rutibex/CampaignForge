from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Any
import random
import time

from campaign_forge.plugins.hexmap.generator import BUILTIN_THEMES, generate_hex_content
from campaign_forge.plugins.names.generator import NameGenConfig, generate_names
from campaign_forge.plugins.dungeonmap.generator import DungeonGenConfig, Dungeon, generate_dungeon, dungeon_contents_text
from campaign_forge.plugins.dungeonmap.svg_export import SvgConfig, dungeon_to_svg


@dataclass
class RegionLayer:
    name: str
    theme: str
    terrain: str
    tags: List[str]
    content: Dict[str, List[str]]

@dataclass
class SiteLayer:
    name: str
    site_type: str
    poi: str
    tags: List[str]
    notes: List[str]

@dataclass
class SubSiteLayer:
    name: str
    subsite_type: str
    tags: List[str]
    dungeon: Optional[Dungeon] = None
    dungeon_seed: Optional[int] = None

@dataclass
class FactionLayer:
    name: str
    faction_type: str
    motive: str
    methods: List[str]
    tags: List[str]
    hooks: List[str]

@dataclass
class RumorLayer:
    rumors: List[str]
    tags: List[str]

@dataclass
class LocationStack:
    version: int
    seed: int
    created_utc: str
    region: RegionLayer
    site: SiteLayer
    subsite: SubSiteLayer
    faction: Optional[FactionLayer]
    rumors: Optional[RumorLayer]


_SITE_TYPES = [
    "Ruined Keep", "Abandoned Watchtower", "Sunken Temple", "Witch-Haunted Mill",
    "Cracked Barrow-Mound", "Collapsed Mine", "Desecrated Chapel", "Bandit Stockade",
    "Shattered Observatory", "Half-Buried Fortress", "Forgotten Bathhouse", "Blackened Manor"
]

_SUBSITE_TYPES = [
    "Undercroft Dungeon", "Catacombs", "Caverns", "Sewer-Warrens", "Arcane Vaults",
    "Prison Cells", "Crypt Labyrinth", "Smuggler Tunnels"
]

_FACTION_TYPES = [
    "Broken Garrison", "Bandit Company", "Cult of the Wound-Star", "Goblin Court",
    "Heretical Monks", "Grave-Robbers' Union", "Exiled Knights", "Salvage Guild"
]

_FACTION_MOTIVES = [
    "hold the site as a staging ground",
    "dig for a sealed relic",
    "complete a half-failed ritual",
    "capture travelers and ransom them",
    "hide from a stronger enemy",
    "extract tribute from nearby villages",
    "keep a terrible thing asleep",
    "prepare an imminent raid"
]

_FACTION_METHODS = [
    "tripwires and alarm bells", "decoy fires at night", "false trail markers",
    "ambush tunnels", "poisoned food stores", "bribed informants", "trained beasts",
    "ritual wards and chalk sigils", "sappers and collapse-traps"
]

_RUMOR_TEMPLATES = [
    "A lantern sometimes burns in {site}—but no one is inside.",
    "Old veterans swear {faction} still drills at dusk in {site}.",
    "A seam of strange ore was found beneath {site}; it hums in moonlight.",
    "A map fragment points to a hidden stair in {site}, behind a cracked saint statue.",
    "People disappear near {site} when the wind blows from the {terrain}.",
    "A bell tolls from {site} on nights with no moon; each toll means a death elsewhere.",
    "A merchant claims the quickest route crosses {terrain} but costs 'a memory'.",
    "Something in {site} answers questions—truthfully—once per season."
]


def _tags_for(layer_kind: str, name: str) -> List[str]:
    slug = (name or "").strip().replace(" ", "-")
    return [layer_kind, f"{layer_kind}:{slug}"]

def _pick_weighted(rng: random.Random, weights: Dict[str, float]) -> str:
    items = list(weights.items())
    total = sum(max(0.0, float(w)) for _, w in items) or 1.0
    roll = rng.random() * total
    acc = 0.0
    for k, w in items:
        acc += max(0.0, float(w))
        if roll <= acc:
            return k
    return items[-1][0]

def _name(rng: random.Random, style: str) -> str:
    cfg = NameGenConfig(
        style=style,
        min_syllables=2,
        max_syllables=4,
        allow_apostrophes=False,
        capitalize=True,
        seed=rng.randrange(1_000_000_000),
    )
    cfg.count = 1
    return generate_names(cfg, rng=rng)[0]


def generate_location_stack(
    rng: random.Random,
    *,
    theme: str = "OSR",
    name_style: str = "Fantasy",
    site_type: Optional[str] = None,
    subsite_type: Optional[str] = None,
    attach_dungeon: bool = True,
    dungeon_cfg: Optional[DungeonGenConfig] = None,
    attach_faction: bool = True,
    attach_rumors: bool = True,
    rumor_count: int = 6,
) -> LocationStack:

    theme = theme if theme in BUILTIN_THEMES else "OSR"
    theme_pack = BUILTIN_THEMES[theme]

    region_name = _name(rng, name_style) + " Reach"
    terrain = _pick_weighted(rng, theme_pack.terrain_weights)
    region_tags = _tags_for("Region", region_name) + [
        "LocationStack",
        f"Theme:{theme}",
        f"Terrain:{terrain.replace(' ', '-')}",
    ]

    region_content = generate_hex_content(terrain, rng)

    site_type = site_type or rng.choice(_SITE_TYPES)
    poi = rng.choice(theme_pack.poi_list) if theme_pack.poi_list else "Ruin"
    site_name = f"{site_type} of {_name(rng, name_style)}"
    site_tags = _tags_for("Site", site_name) + region_tags

    site_notes = [
        f"Dominant terrain nearby: **{terrain}**.",
        f"Primary point-of-interest theme: **{poi}**.",
        rng.choice(
            [
                "Smoke rises some evenings, but no one claims to live there.",
                "Local birds refuse to land on the outer walls.",
                "The stones sweat brine after rain.",
                "A low, steady vibration can be felt in the gate arch.",
                "There are too many footprints—some are old, some are fresh, none lead away.",
            ]
        ),
    ]

    subsite_type = subsite_type or rng.choice(_SUBSITE_TYPES)
    subsite_name = f"{subsite_type} beneath {site_name}"
    subsite_tags = _tags_for("SubSite", subsite_name) + site_tags

    d: Optional[Dungeon] = None
    dungeon_seed: Optional[int] = None
    if attach_dungeon:
        dungeon_seed = rng.randrange(1_000_000_000)
        cfg = dungeon_cfg or DungeonGenConfig()
        cfg.seed = dungeon_seed
        d = generate_dungeon(cfg)

    faction_layer: Optional[FactionLayer] = None
    if attach_faction:
        faction_type = rng.choice(_FACTION_TYPES)
        faction_name = f"{faction_type} of {_name(rng, name_style)}"
        motive = rng.choice(_FACTION_MOTIVES)
        methods = rng.sample(_FACTION_METHODS, k=min(3, len(_FACTION_METHODS)))
        faction_tags = _tags_for("Faction", faction_name) + site_tags + ["Faction"]

        hooks = [
            f"They {motive}.",
            rng.choice(
                [
                    "They will bargain if offered a way out that saves face.",
                    "Their leader is not the true power; something below gives the orders.",
                    "They are missing supplies and will lash out unpredictably.",
                    "They have a prisoner who knows a shortcut into the sub-site.",
                ]
            ),
            rng.choice(
                [
                    "Their banner is stitched from old uniforms; each patch is a conquered place.",
                    "They keep meticulous records of 'debts' carved into bone tablets.",
                    "They never speak above a whisper inside the keep.",
                ]
            ),
        ]
        faction_layer = FactionLayer(
            name=faction_name,
            faction_type=faction_type,
            motive=motive,
            methods=methods,
            tags=faction_tags,
            hooks=hooks,
        )

    rumor_layer: Optional[RumorLayer] = None
    if attach_rumors:
        f_name = faction_layer.name if faction_layer else "someone"
        templates = list(_RUMOR_TEMPLATES)
        rng.shuffle(templates)
        rumors = []
        for t in templates[: max(1, min(rumor_count, len(templates)))]:
            rumors.append(t.format(site=site_name, faction=f_name, terrain=terrain))
        rumor_layer = RumorLayer(rumors=rumors, tags=["Rumor", "Rumors"] + site_tags)

    return LocationStack(
        version=1,
        seed=getattr(rng, "_seed", 0),
        created_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        region=RegionLayer(
            name=region_name,
            theme=theme,
            terrain=terrain,
            tags=region_tags,
            content=region_content,
        ),
        site=SiteLayer(
            name=site_name,
            site_type=site_type,
            poi=poi,
            tags=site_tags,
            notes=site_notes,
        ),
        subsite=SubSiteLayer(
            name=subsite_name,
            subsite_type=subsite_type,
            tags=subsite_tags,
            dungeon=d,
            dungeon_seed=dungeon_seed,
        ),
        faction=faction_layer,
        rumors=rumor_layer,
    )


def stack_to_markdown(stack: LocationStack) -> str:
    r = stack.region
    s = stack.site
    ss = stack.subsite
    f = stack.faction
    ru = stack.rumors

    def tag_line(tags: List[str]) -> str:
        return " ".join(f"`{t}`" for t in tags)

    md: List[str] = []
    md.append(f"# Location Stack — {s.name}")
    md.append("")
    md.append(f"*Seed:* **{stack.seed}**  ")
    md.append(f"*Created:* `{stack.created_utc}`")
    md.append("")
    md.append("## Tag Index")
    md.append("")
    md.append(f"- Region: {tag_line(r.tags)}")
    md.append(f"- Site: {tag_line(s.tags)}")
    md.append(f"- Sub-site: {tag_line(ss.tags)}")
    if f:
        md.append(f"- Faction: {tag_line(f.tags)}")
    if ru:
        md.append(f"- Rumors: {tag_line(ru.tags)}")
    md.append("")

    md.append("## Region")
    md.append(f"**{r.name}** — Theme **{r.theme}**, dominant terrain **{r.terrain}**.")
    md.append(f"Tags: {tag_line(r.tags)}")
    md.append("")
    md.append("**Region Content (Hex-style):**")
    md.append("")
    md.append("- Encounters:")
    for x in r.content.get("encounters", []):
        md.append(f"  - {x}")
    hazards = r.content.get("hazards", [])
    if hazards:
        md.append("- Hazards:")
        for x in hazards:
            md.append(f"  - {x}")
    md.append("- Resources:")
    for x in r.content.get("resources", []):
        md.append(f"  - {x}")
    md.append("")

    md.append("## Site")
    md.append(f"**{s.name}** ({s.site_type}) — POI vibe: **{s.poi}**.")
    md.append(f"Tags: {tag_line(s.tags)}")
    md.append("")
    md.append("**Notes:**")
    for n in s.notes:
        md.append(f"- {n}")
    md.append("")

    if f:
        md.append("## Attached Faction")
        md.append(f"**{f.name}** ({f.faction_type})")
        md.append(f"Tags: {tag_line(f.tags)}")
        md.append("")
        md.append("**Methods / Tactics:**")
        for m in f.methods:
            md.append(f"- {m}")
        md.append("")
        md.append("**Hooks:**")
        for h in f.hooks:
            md.append(f"- {h}")
        md.append("")

    if ru:
        md.append("## Rumors")
        md.append(f"Tags: {tag_line(ru.tags)}")
        md.append("")
        for i, rr in enumerate(ru.rumors, 1):
            md.append(f"{i}. {rr}")
        md.append("")

    md.append("## Sub-site")
    md.append(f"**{ss.name}** ({ss.subsite_type})")
    md.append(f"Tags: {tag_line(ss.tags)}")
    if ss.dungeon:
        md.append("")
        md.append(f"*Dungeon seed:* **{ss.dungeon_seed}**")
        md.append("")
        md.append("### Room Key & Contents")
        md.append("")
        md.append(dungeon_contents_text(ss.dungeon))
        md.append("")
    else:
        md.append("")
        md.append("_No dungeon attached._")
        md.append("")

    return "\n".join(md).strip() + "\n"


def stack_to_json(stack: LocationStack) -> Dict[str, Any]:
    data = asdict(stack)
    if stack.subsite.dungeon is not None:
        d = stack.subsite.dungeon
        data["subsite"]["dungeon"] = {
            "width": d.width,
            "height": d.height,
            "rooms": [asdict(r) for r in d.rooms],
            "doors": [asdict(dr) for dr in d.doors],
            "grid": d.grid,
        }
    return data


def dungeon_svg_bytes(stack: LocationStack, *, cell_size: int = 10) -> Optional[bytes]:
    if not stack.subsite.dungeon:
        return None
    svg = dungeon_to_svg(stack.subsite.dungeon, SvgConfig(cell_size=cell_size, margin=12, draw_room_ids=True))
    return svg.encode("utf-8")
