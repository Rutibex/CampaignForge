from __future__ import annotations

from typing import Any, Dict, List
from pathlib import Path


def _md_header(title: str, level: int = 1) -> str:
    return f"{'#' * max(1, level)} {title}\n"


def _md_kv(k: str, v: str) -> str:
    v = (v or "").strip()
    return f"- **{k}:** {v}\n" if v else f"- **{k}:** —\n"


def faction_to_markdown(faction: Dict[str, Any], *, include_secrets: bool = True) -> str:
    name = faction.get("name", "Unnamed Faction")
    out: List[str] = []
    out.append(_md_header(name, 1))

    out.append(_md_header("Overview", 2))
    out.append(_md_kv("Type", str(faction.get("type", ""))))
    out.append(_md_kv("Ethos", str(faction.get("ethos", ""))))
    out.append(_md_kv("Threat", str(faction.get("threat", ""))))
    out.append(_md_kv("Tone", str(faction.get("tone", ""))))
    out.append(_md_kv("Motto", str(faction.get("motto", ""))))
    out.append(_md_kv("Public Face", str(faction.get("public_face", ""))))
    if include_secrets:
        out.append(_md_kv("Hidden Truth", str(faction.get("hidden_truth", ""))))
    tags = faction.get("tags") or []
    if tags:
        out.append(_md_kv("Tags", ", ".join(tags)))
    notes = (faction.get("notes") or "").strip()
    if notes:
        out.append("\n" + _md_header("Notes", 2) + notes + "\n")

    # Goals
    out.append(_md_header("Goals", 2))
    goals = faction.get("goals") or []
    if not goals:
        out.append("_No goals defined._\n")
    else:
        for g in goals:
            out.append(_md_header(f"{g.get('type','Goal')}: {g.get('description','').strip() or '—'}", 3))
            out.append(_md_kv("Priority", str(g.get("priority",""))))
            out.append(_md_kv("Visibility", str(g.get("visibility",""))))
            out.append(_md_kv("Progress", f"{g.get('progress',0)}%"))
            if include_secrets:
                out.append(_md_kv("Deadline", str(g.get("deadline",""))))
                succ = (g.get("success") or "").strip()
                fail = (g.get("failure") or "").strip()
                if succ:
                    out.append(f"- **On Success:** {succ}\n")
                if fail:
                    out.append(f"- **On Failure:** {fail}\n")
            out.append("\n")

    # Assets
    out.append(_md_header("Assets", 2))
    assets = faction.get("assets") or []
    if not assets:
        out.append("_No assets defined._\n")
    else:
        for a in assets:
            out.append(_md_header(f"{a.get('category','Asset')}: {a.get('name','—')}", 3))
            out.append(_md_kv("Security", str(a.get("security",""))))
            out.append(_md_kv("Mobility", str(a.get("mobility",""))))
            out.append(_md_kv("Known", str(a.get("known",""))))
            atags = a.get("tags") or []
            if atags:
                out.append(_md_kv("Tags", ", ".join(atags)))
            anotes = (a.get("notes") or "").strip()
            if anotes:
                out.append(f"\n{anotes}\n")
            out.append("\n")

    # Relationships
    out.append(_md_header("Relationships", 2))
    rels = faction.get("relationships") or []
    if not rels:
        out.append("_No relationships defined._\n")
    else:
        for r in rels:
            out.append(f"- **{r.get('type','Relation')}:** {r.get('target','—')} (Tension: {r.get('tension','—')})\n")
            if include_secrets:
                h = (r.get("history") or "").strip()
                if h:
                    out.append(f"  - {h}\n")

    out.append("\n")

    # Schisms
    out.append(_md_header("Internal Schisms", 2))
    schisms = faction.get("schisms") or []
    if not schisms:
        out.append("_No schisms defined._\n")
    else:
        for s in schisms:
            out.append(_md_header(str(s.get("type","Schism")), 3))
            fparts = s.get("factions") or []
            if fparts:
                for p in fparts:
                    out.append(f"- **{p.get('name','—')}**: {p.get('power',0)}%\n")
                    ag = (p.get("agenda") or "").strip()
                    if include_secrets and ag:
                        out.append(f"  - {ag}\n")
            out.append(_md_kv("Clock", str(s.get("clock",""))))
            if include_secrets:
                fp = (s.get("flashpoint") or "").strip()
                oc = (s.get("outcome") or "").strip()
                if fp:
                    out.append(f"- **Flashpoint:** {fp}\n")
                if oc:
                    out.append(f"- **Outcome:** {oc}\n")
                sn = (s.get("notes") or "").strip()
                if sn:
                    out.append(f"\n{sn}\n")
            out.append("\n")

    # Timeline
    out.append(_md_header("Timeline", 2))
    tl = faction.get("timeline") or []
    if not tl:
        out.append("_No timeline events defined._\n")
    else:
        for ev in tl:
            out.append(f"- **{ev.get('created','')}** — {ev.get('title','—')}\n")
            det = (ev.get("details") or "").strip()
            if det:
                out.append(f"  - {det}\n")
            tags = ev.get("tags") or []
            if tags:
                out.append(f"  - Tags: {', '.join(tags)}\n")

    out.append("\n")
    return "".join(out)


def build_gm_packet(faction: Dict[str, Any]) -> Dict[str, str]:
    # filename -> markdown content
    gm = faction_to_markdown(faction, include_secrets=True)
    player = faction_to_markdown(faction, include_secrets=False)

    name = (faction.get("name") or "faction").strip()
    slug = "".join(ch for ch in name.lower() if ch.isalnum() or ch in ("-", "_", " ")).strip().replace(" ", "_")[:48] or "faction"
    return {
        f"{slug}_gm.md": gm,
        f"{slug}_player.md": player,
    }
