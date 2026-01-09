from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from . import tables


@dataclass
class MagicItem:
    name: str
    item_type: str
    theme: str
    rarity: str
    power_tier: str
    effect_category: str
    effect: str
    drawback_type: str
    drawback: str
    quirk: str
    origin: str
    twist: str
    seed: int
    created_utc: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_markdown(self) -> str:
        # Keep it GM-ready, printable, and scratchpad-friendly.
        return (
            f"# {self.name}\n\n"
            f"**Type:** {self.item_type}\n\n"
            f"**Theme:** {self.theme}\n\n"
            f"**Rarity:** {self.rarity}\n\n"
            f"**Power Tier:** {self.power_tier}\n\n"
            f"**Effect ({self.effect_category}):** {self.effect}\n\n"
            f"**Drawback ({self.drawback_type}):** {self.drawback}\n\n"
            f"**Quirk:** {self.quirk}\n\n"
            f"**Origin:** {self.origin}\n\n"
            f"**Twist:** {self.twist}\n\n"
            f"---\n"
            f"**Seed:** `{self.seed}`  \n"
            f"**Generated:** {self.created_utc}\n"
        )


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _pick(rng, seq):
    return seq[rng.randrange(0, len(seq))]


def _pick_weighted_power(rng, power: int) -> str:
    """
    power: 0..100 slider
    Bias toward higher tiers when power is high.
    """
    # Map to a "target tier" 0..4
    target = max(0, min(4, round((power / 100) * 4)))
    # weights favor target, but allow neighbors
    weights = [1, 1, 1, 1, 1]
    for i in range(5):
        dist = abs(i - target)
        weights[i] = max(1, 5 - 2 * dist)  # 5,3,1,1,1 shape
    # draw
    total = sum(weights)
    roll = rng.randrange(1, total + 1)
    acc = 0
    for i, w in enumerate(weights):
        acc += w
        if roll <= acc:
            return tables.POWER_TIERS[i][0]
    return tables.POWER_TIERS[target][0]


def _curse_chance(risk: int, allow_curse: bool) -> bool:
    if not allow_curse:
        return False
    # risk 0..100 -> curse probability up to ~70%
    return risk >= 10


def _choose_drawback(rng, risk: int, allow_curse: bool):
    # With low risk, sometimes no drawback (but still often include one, OSR style).
    # We'll always include a drawback, but make it softer at low risk by picking
    # less punishing categories more often.
    # (You can later expand this to “no drawback” if you want.)
    return _pick(rng, tables.DRAWBACKS)


def _name(rng) -> str:
    prefix = _pick(rng, tables.NAME_PREFIX)
    noun = _pick(rng, tables.NAME_NOUN)
    # 70% include epithet
    if rng.random() < 0.7:
        epithet = _pick(rng, tables.NAME_EPITHET)
        return f"{prefix} {noun} {epithet}"
    return f"{prefix} {noun}"


def generate_magic_item(
    rng,
    *,
    theme: Optional[str] = None,
    item_type: Optional[str] = None,
    power: int = 50,
    risk: int = 50,
    weirdness: int = 50,
    allow_curse: bool = True,
    rarity: Optional[str] = None,
    seed_used: int = 0,
) -> MagicItem:
    theme = theme or _pick(rng, tables.THEMES)
    item_type = item_type or _pick(rng, tables.ITEM_TYPES)
    rarity = rarity or _pick(rng, tables.RARITIES)

    power_tier = _pick_weighted_power(rng, power)

    # Effects: bias toward “weirder” categories as weirdness rises
    if rng.random() < (weirdness / 100) * 0.35:
        category = _pick(rng, ["Time/Fate", "Planar", "Transformation", "Environment"])
    else:
        category = _pick(rng, tables.EFFECT_CATEGORIES)

    # pick effect from category if possible
    matching = [e for e in tables.EFFECTS if e[0] == category]
    if not matching:
        matching = tables.EFFECTS
    effect_category, effect = _pick(rng, matching)

    drawback_type, drawback = _choose_drawback(rng, risk, allow_curse)
    quirk = _pick(rng, tables.QUIRKS)
    origin = _pick(rng, tables.ORIGINS)

    twist = _pick(rng, tables.TWISTS)
    # Increase twist density slightly with weirdness
    if rng.random() < (weirdness / 100) * 0.25:
        twist = f"{twist} Also: {_pick(rng, tables.TWISTS)}"

    name = _name(rng)

    return MagicItem(
        name=name,
        item_type=item_type,
        theme=theme,
        rarity=rarity,
        power_tier=power_tier,
        effect_category=effect_category,
        effect=effect,
        drawback_type=drawback_type,
        drawback=drawback,
        quirk=quirk,
        origin=origin,
        twist=twist,
        seed=seed_used,
        created_utc=_now_utc_iso(),
    )
