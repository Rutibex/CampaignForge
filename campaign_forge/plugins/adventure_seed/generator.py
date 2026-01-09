from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple
import json
import time
import uuid


# -----------------------------
# Data models
# -----------------------------

@dataclass
class AdventureSettings:
    tone: str = "neutral"         # grim | neutral | pulp | weird
    scope: str = "one_session"    # one_session | mini_arc
    danger: int = 50              # 0-100
    title_hint: str = ""          # optional user hint


@dataclass
class AdventureComponent:
    type: str
    data: Dict[str, Any]


@dataclass
class AdventureSeed:
    seed_id: str
    generated_at: str
    master_seed: int
    derived_seed: int
    iteration: int
    settings: AdventureSettings
    hook: AdventureComponent
    location: AdventureComponent
    antagonist: AdventureComponent
    twist: AdventureComponent
    clock: AdventureComponent
    tags: List[str]

    def to_jsonable(self) -> Dict[str, Any]:
        d = asdict(self)
        # dataclasses nested are fine
        return d


# -----------------------------
# Table loading
# -----------------------------

def load_tables(tables_path: Path) -> Dict[str, Any]:
    """
    Load tables JSON. Caller should handle exceptions.
    """
    return json.loads(tables_path.read_text(encoding="utf-8"))


def _weighted_choice(rng, items: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    # items contain 'weight' optional
    total = 0.0
    weights = []
    for it in items:
        w = float(it.get("weight", 1.0))
        if w < 0:
            w = 0.0
        weights.append(w)
        total += w
    if total <= 0:
        # fallback uniform
        return dict(items[int(rng.random() * len(items))])
    r = rng.random() * total
    acc = 0.0
    for it, w in zip(items, weights):
        acc += w
        if r <= acc:
            return dict(it)
    return dict(items[-1])


def _filter_by_tone(items: Sequence[Dict[str, Any]], tone: str) -> List[Dict[str, Any]]:
    tone = (tone or "any").lower()
    out = []
    for it in items:
        tones = [t.lower() for t in (it.get("tone") or ["any"])]
        if "any" in tones or tone in tones:
            out.append(it)
    return out or list(items)


def _filter_by_scope(items: Sequence[Dict[str, Any]], scope: str) -> List[Dict[str, Any]]:
    scope = (scope or "").lower()
    out = []
    for it in items:
        scopes = [s.lower() for s in (it.get("scope") or [])]
        if not scopes or scope in scopes:
            out.append(it)
    return out or list(items)


def _format_template(obj: Any, fragments: Dict[str, List[str]], rng) -> Any:
    """
    Recursively format strings with fragment placeholders, choosing fragment values deterministically.
    For each placeholder key, we pick a value using rng.
    """
    if isinstance(obj, str):
        # Find {keys} and substitute
        def repl(match):
            key = match.group(1)
            vals = fragments.get(key, None)
            if not vals:
                return match.group(0)
            return str(vals[int(rng.random() * len(vals))])
        import re
        return re.sub(r"\{([a-zA-Z0-9_]+)\}", repl, obj)
    elif isinstance(obj, list):
        return [_format_template(x, fragments, rng) for x in obj]
    elif isinstance(obj, dict):
        return {k: _format_template(v, fragments, rng) for k, v in obj.items()}
    else:
        return obj


def _make_seed_id() -> str:
    # stable-ish but unique: time + short uuid
    return f"ASEED-{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"


# -----------------------------
# Generation
# -----------------------------

def generate_adventure_seed(*,
    rng,
    master_seed: int,
    derived_seed: int,
    iteration: int,
    settings: AdventureSettings,
    tables: Dict[str, Any],
    lock: Optional[Dict[str, bool]] = None,
    previous: Optional[AdventureSeed] = None
) -> AdventureSeed:
    """
    Generate a cohesive adventure seed. If lock flags are set, reuse the corresponding component
    from 'previous' when available.
    """
    lock = dict(lock or {})
    fragments = dict((tables.get("fragments") or {}))

    def choose_component(kind: str, picker_items: List[Dict[str, Any]], extra_filters=None) -> AdventureComponent:
        items = _filter_by_tone(picker_items, settings.tone)
        if extra_filters:
            items = extra_filters(items)
        base = _weighted_choice(rng, items)
        base = dict(base)
        base.pop("weight", None)
        # Expand templates
        expanded = _format_template(base, fragments, rng)
        ctype = str(expanded.get("type", kind)).strip() or kind
        expanded.pop("type", None)
        return AdventureComponent(type=ctype, data=expanded)

    # Components
    hook = None
    location = None
    antagonist = None
    twist = None
    clock = None

    if lock.get("hook") and previous:
        hook = previous.hook
    else:
        hook = choose_component("Hook", list(tables.get("hooks", [])))

    if lock.get("location") and previous:
        location = previous.location
    else:
        location = choose_component("Location", list(tables.get("locations", [])))

    if lock.get("antagonist") and previous:
        antagonist = previous.antagonist
    else:
        antagonist = choose_component("Antagonist", list(tables.get("antagonists", [])))

    if lock.get("twist") and previous:
        twist = previous.twist
    else:
        twist = choose_component("Twist", list(tables.get("twists", [])))

    if lock.get("clock") and previous:
        clock = previous.clock
    else:
        def scope_filter(items):
            return _filter_by_scope(items, settings.scope)
        clock = choose_component("Clock", list(tables.get("clocks", [])), extra_filters=scope_filter)

    tags = ["AdventureSeed"]
    # Heuristic tags based on location/antagonist
    try:
        loc_type = (location.type or "").replace(" ", "")
        if loc_type:
            tags.append(loc_type)
    except Exception:
        pass
    try:
        if antagonist.type.lower() == "faction":
            name = antagonist.data.get("name", "")
            if name:
                # Make a safe tag
                safe = "".join(ch for ch in name if ch.isalnum() or ch in (" ", "-", "_")).strip().replace(" ", "")
                if safe:
                    tags.append(f"Faction:{safe[:32]}")
    except Exception:
        pass
    if settings.scope == "one_session":
        tags.append("OneShot")
    elif settings.scope == "mini_arc":
        tags.append("MiniArc")

    seed = AdventureSeed(
        seed_id=_make_seed_id(),
        generated_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
        master_seed=int(master_seed),
        derived_seed=int(derived_seed),
        iteration=int(iteration),
        settings=settings,
        hook=hook,
        location=location,
        antagonist=antagonist,
        twist=twist,
        clock=clock,
        tags=tags,
    )
    return seed


def seed_to_markdown(seed: AdventureSeed) -> str:
    s = seed
    # Nice title: use location name if present
    loc_name = ""
    try:
        loc_name = str(s.location.data.get("name", "")).strip()
    except Exception:
        loc_name = ""
    title = loc_name or "Tonight's Adventure"

    def md_component(label: str, comp: AdventureComponent) -> str:
        lines = [f"## {label} — {comp.type}"]
        for k, v in (comp.data or {}).items():
            if v is None or v == "":
                continue
            key = k.replace("_", " ").strip().title()
            if isinstance(v, list):
                vv = ", ".join(str(x) for x in v)
            else:
                vv = str(v)
            lines.append(f"**{key}:** {vv}")
        return "\n".join(lines)

    # Danger hint
    danger = s.settings.danger
    if danger < 25: danger_word = "Low"
    elif danger < 60: danger_word = "Moderate"
    elif danger < 85: danger_word = "High"
    else: danger_word = "Lethal"

    md = []
    md.append(f"# Adventure Seed: {title}")
    md.append("")
    md.append(f"*Seed:* `{s.derived_seed}`  |  *Tone:* **{s.settings.tone}**  |  *Scope:* **{s.settings.scope}**  |  *Danger:* **{danger_word} ({danger})**")
    md.append("")
    md.append(md_component("Hook", s.hook))
    md.append("")
    md.append(md_component("Location", s.location))
    md.append("")
    md.append(md_component("Antagonist", s.antagonist))
    md.append("")
    md.append(md_component("Twist", s.twist))
    md.append("")
    # Clock special formatting
    md.append(f"## Countdown Clock — {s.clock.type}")
    stages = s.clock.data.get("stages", [])
    triggers = s.clock.data.get("advance_triggers", [])
    if stages:
        md.append("**Stages:**")
        for i, st in enumerate(stages, 1):
            md.append(f"{i}. {st}")
    if triggers:
        md.append("")
        md.append("**Advances when:** " + ", ".join(str(x) for x in triggers))
    md.append("")
    if s.tags:
        md.append("**Tags:** " + ", ".join(s.tags))
    return "\n".join(md).strip() + "\n"
