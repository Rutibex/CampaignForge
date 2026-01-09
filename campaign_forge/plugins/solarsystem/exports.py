from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional, Tuple
import json
import datetime

from .generator import iter_bodies, summarize_world


def _safe_slug(s: str) -> str:
    s = (s or "system").strip().lower()
    out = []
    for ch in s:
        if ch.isalnum():
            out.append(ch)
        elif ch in (" ", "-", "_"):
            out.append("-")
    slug = "".join(out).strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug[:60] or "system"


def system_overview_markdown(system: Dict[str, Any]) -> str:
    hz = system.get("habitable_zone", {})
    lines = []
    lines.append(f"# {system.get('name','Solar System')}\n")
    stars = system.get("stars", [])
    lines.append("## Stars")
    for s in stars:
        st = s.get("type", {})
        lines.append(f"- **{s.get('name','(star)')}** — {st.get('name','Unknown')} ({s.get('role','')})")
    lines.append("")
    lines.append(f"## Habitable Zone\n- Inner: {hz.get('inner','?')} AU\n- Outer: {hz.get('outer','?')} AU\n")
    if system.get("gm_notes"):
        lines.append("## GM Notes")
        for n in system["gm_notes"]:
            lines.append(f"- {n}")
        lines.append("")
    lines.append("## Worlds")
    for p in system.get("orbits", []):
        lines.append(f"### {p.get('name','(planet)')} — {p.get('class',{}).get('name','World')}")
        lines.append(f"- Orbit: {p.get('au','?')} AU (Index {p.get('orbit_index','?')})")
        lines.append(f"- Life: {'Yes' if p.get('has_life') else 'No'}")
        lines.append(f"- Inhabited: {'Yes' if p.get('inhabited') else 'No'}")
        if p.get("notes"):
            for n in p["notes"]:
                lines.append(f"- {n}")
        if p.get("moons"):
            lines.append("- Moons:")
            for m in p["moons"]:
                lines.append(f"  - {m.get('name')} — {m.get('class',{}).get('name','Moon')} (Life: {'Yes' if m.get('has_life') else 'No'}, Inhabited: {'Yes' if m.get('inhabited') else 'No'})")
        lines.append("")
    if system.get("routes"):
        lines.append("## Trade & Travel")
        rid = {b.get('id'): b.get('name') for b in iter_bodies(system)}
        for r in system.get('routes', []) or []:
            lines.append(f"- {rid.get(r.get('from'), r.get('from'))} ↔ {rid.get(r.get('to'), r.get('to'))} ({r.get('kind','route')})")
        lines.append("")

    if system.get("belts"):
        lines.append("## Belts & Minor Bodies")
        for b in system["belts"]:
            lines.append(f"- {b.get('name')} — {b.get('kind')} at ~{b.get('au')} AU")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def world_markdown(body: Dict[str, Any]) -> str:
    # Uses generator.summarize_world for a compact block, then expands.
    cls = body.get("class", {}).get("name", "World")
    uwp = body.get("uwp", {})
    lines = []
    lines.append(f"# {body.get('name','(world)')}\n")
    lines.append(f"**Type:** {cls}  ")
    lines.append(f"**Orbit:** {body.get('au','?')} AU (Index {body.get('orbit_index','?')})  ")
    lines.append(f"**Life:** {'Yes' if body.get('has_life') else 'No'}  ")
    lines.append(f"**Inhabited:** {'Yes' if body.get('inhabited') else 'No'}\n")
    if uwp:
        lines.append("## Traveller-Style Summary (UWP-ish)")
        lines.append("- " + " ".join([
            f"Starport {uwp.get('starport','-')}",
            f"Size {uwp.get('size',0)}",
            f"Atm {uwp.get('atmosphere',0)}",
            f"Hyd {uwp.get('hydro',0)}",
            f"Pop {uwp.get('population',0)}",
            f"Gov {uwp.get('government',0)}",
            f"Law {uwp.get('law',0)}",
            f"TL {uwp.get('tech',0)}",
        ]))
        lines.append("")
    if body.get("biosphere"):
        b = body["biosphere"]
        lines.append("## Life")
        lines.append(f"- **{b.get('name','Life')}**: {b.get('summary','')}\n")
    if body.get("culture"):
        c = body["culture"]
        lines.append("## Culture")
        lines.append(f"- **{c.get('name','Culture')}** — {c.get('vibe','')}")
        tags = c.get("tags") or []
        if tags:
            lines.append(f"- Tags: {', '.join(tags)}")
        lines.append("")
    if body.get("government"):
        g = body["government"]
        lines.append("## Government")
        lines.append(f"- **{g.get('name','Gov')}** — {g.get('hook','')}")
        lines.append("")
    if body.get("hazards"):
        lines.append("## Hazards")
        for h in body["hazards"]:
            lines.append(f"- **{h.get('name','Hazard')}**: {h.get('effect','')}")
        lines.append("")
    if body.get("trade"):
        lines.append("## Trade Goods")
        for t in body["trade"]:
            lines.append(f"- **{t.get('name','Good')}**: {t.get('notes','')}")
        lines.append("")
    if body.get("notes"):
        lines.append("## Notes & Hooks")
        for n in body["notes"]:
            lines.append(f"- {n}")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def _create_session_pack(ctx, slug: str, seed: Optional[int]) -> Path:
    # Preferred: ctx.export_manager.create_session_pack(plugin_id, seed=seed)
    em = getattr(ctx, "export_manager", None)
    if em and hasattr(em, "create_session_pack"):
        return em.create_session_pack("solarsystem", seed=seed, slug=slug)

    # Fallback: make a directory under exports/session_packs
    project_dir = getattr(ctx, "project_dir", None) or getattr(ctx, "project_root", None)
    if project_dir is None:
        project_dir = Path.cwd()
    else:
        project_dir = Path(project_dir)

    ts = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
    seed_part = f"_seed{seed}" if seed is not None else ""
    pack = project_dir / "exports" / "session_packs" / f"{ts}_{slug}{seed_part}"
    pack.mkdir(parents=True, exist_ok=True)
    return pack


def export_system_pack(
    ctx,
    system: Dict[str, Any],
    *,
    seed: Optional[int],
    map_png_bytes: Optional[bytes],
    map_svg_bytes: Optional[bytes],
) -> Path:
    slug = _safe_slug(system.get("name", "system"))
    pack = _create_session_pack(ctx, slug, seed)

    # Overview + raw json
    (pack / "system_overview.md").write_text(system_overview_markdown(system), encoding="utf-8")
    (pack / "system.json").write_text(json.dumps(system, indent=2), encoding="utf-8")

    # Worlds
    worlds_dir = pack / "worlds"
    worlds_dir.mkdir(exist_ok=True)
    for body in iter_bodies(system):
        fname = _safe_slug(body.get("name", "world")) + ".md"
        (worlds_dir / fname).write_text(world_markdown(body), encoding="utf-8")

    # Map exports
    if map_png_bytes:
        (pack / "system_map.png").write_bytes(map_png_bytes)
    if map_svg_bytes:
        (pack / "system_map.svg").write_bytes(map_svg_bytes)

    return pack
