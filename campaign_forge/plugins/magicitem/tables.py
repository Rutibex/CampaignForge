"""
Starter content tables for magic item generation.

Designed to be:
- system-agnostic (OSR-friendly)
- flavorful, not math-heavy
- easily expandable
"""

THEMES = [
    "Grim Relics", "Weird Arcana", "Fae Bargains", "Holy Remnants", "Demon-Forged",
    "Stormcraft", "Deep Dungeons", "Necromantic", "Witchcraft", "Planar Oddities",
    "Clockwork", "Mythic", "Forbidden Lore",
]

ITEM_TYPES = [
    "Weapon", "Armor", "Shield", "Wand", "Staff", "Ring", "Amulet", "Cloak",
    "Boots", "Helm", "Belt", "Gloves", "Tool", "Book", "Idol", "Key", "Consumable",
    "Wondrous Item", "Relic", "Artifact",
]

POWER_TIERS = [
    ("Trivial", 0),
    ("Useful", 1),
    ("Dangerous", 2),
    ("World-altering", 3),
    ("Catastrophic", 4),
]

RARITIES = [
    "Common", "Uncommon", "Rare", "Singular", "Mythic",
]

EFFECT_CATEGORIES = [
    "Combat", "Movement", "Survival", "Information", "Social", "Summoning",
    "Transformation", "Time/Fate", "Planar", "Environment",
]

# Each entry is (category, effect_text)
EFFECTS = [
    ("Combat", "Cuts through non-living matter as if it were soft wood (stone, iron, bone)."),
    ("Combat", "Marks a target you can see; allies can track it unerringly for a day."),
    ("Combat", "Once per fight, ignore the first injury you would take—then feel it after the fight ends."),
    ("Combat", "Your strikes leave a visible afterimage; foes hesitate (briefly) before closing."),
    ("Movement", "Step between two shadows you can see (but something may step back)."),
    ("Movement", "Walk across fragile surfaces (ice, glass, thin branches) as if they were solid."),
    ("Movement", "Once per day, leap an impossible distance—landings always leave a sign."),
    ("Survival", "Neutralizes one poison or rot per day—your breath smells of it afterward."),
    ("Survival", "Creates a palm-sized ember that never dies; it attracts hungry things."),
    ("Survival", "Purifies a waterskin’s worth of liquid, but turns it faintly luminous."),
    ("Information", "Whispers the last lie spoken in a room (not who spoke it)."),
    ("Information", "Reveals hidden doors by outlining them in frost for a minute."),
    ("Information", "Shows the ‘nearest regret’ of a creature you touch (often dangerous knowledge)."),
    ("Social", "Your voice carries authority—people assume you have a right to be here."),
    ("Social", "You can speak a person’s true name once; they will remember it forever."),
    ("Social", "Turns a sincere compliment into a binding promise (for both parties)."),
    ("Summoning", "Calls a small helper spirit for a task; it demands payment in memories."),
    ("Summoning", "Summons a flock of harmless birds that always point toward home."),
    ("Transformation", "Lets you shed your skin once; you emerge altered in a subtle way."),
    ("Transformation", "You may become mist for a breath; afterward you taste smoke for hours."),
    ("Time/Fate", "Once per day, redo the last few heartbeats—but something else claims the discarded outcome."),
    ("Time/Fate", "In the moment of decision, you see two futures; choosing one stains you with its consequence."),
    ("Planar", "Opens a thumb-wide crack into ‘elsewhere’—useful, but watched."),
    ("Planar", "Makes sacred ground feel like home, and home feel… distant."),
    ("Environment", "Causes plants to grow toward you; doors swell, ropes tighten, roots creep."),
    ("Environment", "Silences an area briefly; afterwards sound returns as a violent echo."),
]

QUIRKS = [
    "Always slightly warm, like it was held near a fire.",
    "Smells of ozone before danger.",
    "Animals avoid the bearer unless fed first.",
    "Leaves faint footprints even when you float or fly.",
    "Whispers advice at night (half of it is terrible).",
    "Cannot be fully concealed; it ‘wants’ to be seen.",
    "Stains water black when washed.",
    "Grows cold near lies.",
    "Hums when pointed at something valuable.",
    "Its shadow moves a fraction behind your own.",
]

DRAWBACKS = [
    ("Physical", "Each use steals a little heat: your fingers go numb until you rest."),
    ("Physical", "After using it, you cough up black dust for an hour."),
    ("Social", "People feel watched around you; hospitality becomes expensive."),
    ("Social", "Any oath you swear is taken literally and punished if broken."),
    ("Temporal", "Using it shaves a few minutes from your day; you ‘lose time’ in small ways."),
    ("Temporal", "Each use advances a personal ‘aging’ mark (subtle, but cumulative)."),
    ("Attention", "A hunter (mortal or not) becomes aware of your location for a night."),
    ("Attention", "Spirits take an interest; small hauntings follow for a week."),
    ("Moral", "It offers solutions that require cruelty; refusing makes it sulk and misbehave."),
    ("Moral", "Each use asks you to name someone you’ve wronged; your voice shakes until you do."),
    ("Environmental", "Nearby metal tarnishes; locks become unreliable for a day."),
    ("Environmental", "Candles gutter and die when you draw it."),
    ("Consumption", "It must be ‘fed’ something small: a coin, a secret, a drop of blood."),
    ("Consumption", "It eats written words: the next page you read becomes blank."),
]

ORIGINS = [
    "Forged from the broken crown of a drowned king.",
    "Woven from hair stolen from a sleeping saint.",
    "Carved from a meteorite that sang as it fell.",
    "Made by a witch who never used the same name twice.",
    "Cast in a hell foundry; quenched in holy water.",
    "Grown, not made: a living thing that learned to be an item.",
    "Built by a clockmaker who tried to trap a moment of joy.",
    "Gifted by the fae as payment for a promise you don’t remember making.",
    "Recovered from a sealed vault labeled ONLY: ‘DO NOT WIN.’",
    "Once belonged to the last explorer of a map that eats itself.",
]

# Some "twists" give the generator punch without needing hard rules.
TWISTS = [
    "The benefit is real, but it always leaves evidence.",
    "It works flawlessly—until you use it for selfish reasons.",
    "It’s strongest when you’re afraid.",
    "It refuses to function in sunlight.",
    "It hungers for a particular kind of story (revenge, romance, betrayal).",
    "It’s being used by someone else at the same time, somewhere far away.",
    "It ‘learns’ from you and becomes more like you (for good or ill).",
    "It is quietly replacing something in your life.",
]

# “Name bits” for a simple but effective naming system.
NAME_PREFIX = [
    "Ashen", "Gilded", "Hollow", "Sable", "Radiant", "Veil", "Iron", "Ivory",
    "Sorrow", "Mercy", "Thorn", "Wound", "Cinder", "Moon", "Root", "Oath",
    "Grave", "Whisper", "Gale", "Witch",
]
NAME_NOUN = [
    "Key", "Crown", "Lantern", "Blade", "Bell", "Mask", "Chain", "Mirror",
    "Needle", "Cup", "Book", "Stone", "Ring", "Cloak", "Compass", "Chime",
    "Seal", "Coin", "Bone", "Thread",
]
NAME_EPITHET = [
    "of the Third Dawn", "of Unquiet Waters", "of Borrowed Breath", "of the Last Door",
    "of the Pale Court", "of the Devouring Map", "of Black Candles", "of the Quiet War",
    "of Waking Regret", "of Saints That Lie", "of the Crooked Star", "of the Witch Road",
]
