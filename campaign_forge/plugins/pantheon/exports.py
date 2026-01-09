from __future__ import annotations

from typing import Dict, List
from pathlib import Path
import json

from .generator import Pantheon, pantheon_to_dict


def _md_escape(s: str) -> str:
    return s.replace("\r", "").strip()


def _god_md(g) -> str:
    prim = ", ".join(g.domains_primary) if g.domains_primary else "—"
    sec = ", ".join(g.domains_secondary) if g.domains_secondary else "—"
    forb = ", ".join(g.forbidden) if g.forbidden else "—"
    titles = "; ".join(g.titles) if g.titles else "—"
    offerings = ", ".join(g.offerings) if g.offerings else "—"
    virtues = ", ".join(g.virtues) if g.virtues else "—"
    vices = ", ".join(g.vices) if g.vices else "—"

    return "\n".join([
        f"# {g.name}",
        "",
        f"**Tier:** {g.tier}",
        f"**Titles:** {titles}",
        f"**Epithet:** {g.epithet}",
        "",
        "## Domains",
        f"- **Primary:** {prim}",
        f"- **Secondary:** {sec}",
        f"- **Forbidden:** {forb}",
        "",
        "## Temperament and Motives",
        f"- **Temperament:** {g.temperament}",
        f"- **Desire:** {g.desire}",
        f"- **Flaw:** {g.flaw}",
        f"- **Taboo:** {g.taboo}",
        "",
        "## Iconography",
        f"- **Symbol:** {g.icon_symbol}",
        f"- **Sacred Animal:** {g.icon_animal}",
        f"- **Sacred Material:** {g.icon_material}",
        f"- **Holy Day:** {g.holy_day}",
        "",
        "## Worship",
        f"- **Style:** {g.worship_style}",
        f"- **Offerings:** {offerings}",
        f"- **Clergy:** {g.clergy}",
        "",
        "## Virtues & Vices",
        f"- **Virtues:** {virtues}",
        f"- **Vices:** {vices}",
        "",
        "## Myth Fragments",
        f"- **Origin:** {_md_escape(g.origin_myth)}",
        f"- **Greatest Victory:** {_md_escape(g.victory)}",
        f"- **Greatest Failure:** {_md_escape(g.failure)}",
        f"- **Greatest Sin:** {_md_escape(g.sin)}",
        f"- **What Mortals Believe:** {_md_escape(g.mortal_belief)}",
        "",
    ])


def pantheon_overview_md(p: Pantheon) -> str:
    lines = []
    lines.append(f"# Pantheon: {p.name}")
    lines.append("")
    lines.append(f"- **Tone:** {p.tone}")
    lines.append(f"- **Involvement:** {p.involvement}")
    lines.append(f"- **Structure:** {p.structure}")
    lines.append(f"- **Seed:** {p.seed}")
    lines.append(f"- **Iteration:** {p.iteration}")
    lines.append("")
    lines.append("## Metrics")
    for k, v in p.metrics.items():
        lines.append(f"- **{k.replace('_', ' ').title()}:** {v}")
    lines.append("")
    lines.append("## Gods")
    for g in p.gods:
        dom = ", ".join(g.domains_primary + g.domains_secondary)
        lines.append(f"- **{g.name}** ({g.tier}) — {dom}")
    lines.append("")
    return "\n".join(lines)


def relationships_md(p: Pantheon, god_name_by_id: Dict[str, str]) -> str:
    lines = []
    lines.append("# Divine Relationships")
    lines.append("")
    for r in p.relationships:
        a = god_name_by_id.get(r.a, r.a)
        b = god_name_by_id.get(r.b, r.b)
        lines.append(f"## {a} ↔ {b}")
        lines.append(f"- **Type:** {r.rel_type}")
        lines.append(f"- **Intensity:** {r.intensity}/5")
        lines.append(f"- **Status:** {r.status}")
        if r.a_to_b_note:
            lines.append(f"- **{a} → {b}:** {r.a_to_b_note}")
        if r.b_to_a_note:
            lines.append(f"- **{b} → {a}:** {r.b_to_a_note}")
        lines.append(f"- **Secret:** {r.secret}")
        lines.append("")
    return "\n".join(lines)


def conflicts_md(p: Pantheon, god_name_by_id: Dict[str, str]) -> str:
    lines = []
    lines.append("# Active Divine Conflicts")
    lines.append("")
    if not p.conflicts:
        lines.append("_No major conflicts detected. (Either a calm age… or a masked one.)_")
        lines.append("")
        return "\n".join(lines)

    for c in p.conflicts:
        names = [god_name_by_id.get(gid, gid) for gid in c.gods_involved]
        lines.append(f"## {c.title}")
        lines.append(f"- **Gods:** {', '.join(names)}")
        lines.append(f"- **Cause:** {c.cause}")
        lines.append(f"- **Stakes:** {c.stakes}")
        lines.append(f"- **Escalation:** {c.escalation}")
        lines.append(f"- **Stability Impact:** {c.stability_impact}/5")
        lines.append("")
    return "\n".join(lines)


def export_session_pack(ctx, pantheon: Pantheon) -> Path:
    """
    Creates a session pack and writes:
      - pantheon_overview.md
      - relationships.md
      - conflicts.md
      - gods/<god>.md
      - pantheon.json
    """
    slug = "pantheon_" + pantheon.name.lower().replace(" ", "_")
    pack_dir = ctx.export_manager.create_session_pack(slug, seed=pantheon.seed)

    gods_dir = pack_dir / "gods"
    gods_dir.mkdir(parents=True, exist_ok=True)

    god_name_by_id = {g.gid: g.name for g in pantheon.gods}

    (pack_dir / "pantheon_overview.md").write_text(pantheon_overview_md(pantheon), encoding="utf-8")
    (pack_dir / "relationships.md").write_text(relationships_md(pantheon, god_name_by_id), encoding="utf-8")
    (pack_dir / "conflicts.md").write_text(conflicts_md(pantheon, god_name_by_id), encoding="utf-8")

    for g in pantheon.gods:
        fname = f"{g.name.lower().replace(' ', '_')}.md"
        (gods_dir / fname).write_text(_god_md(g), encoding="utf-8")

    (pack_dir / "pantheon.json").write_text(json.dumps(pantheon_to_dict(pantheon), indent=2), encoding="utf-8")

    return pack_dir
