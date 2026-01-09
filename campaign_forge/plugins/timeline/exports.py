from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional


def _fmt_tags(tags: List[str]) -> str:
    tags = [t.strip() for t in (tags or []) if str(t).strip()]
    if not tags:
        return ""
    return " **Tags:** " + ", ".join(f"`{t}`" for t in tags)


def render_fronts_markdown(state: Dict[str, Any]) -> str:
    """Human-friendly summary of all fronts and their clocks."""
    session = (state.get("session") or {}).get("count")
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    out: List[str] = []
    out.append(f"# Fronts & Clocks Summary\n")
    out.append(f"*Generated:* {now}" + (f"  \n*Session:* {session}" if session is not None else "") + "\n")

    fronts = state.get("fronts") or []
    if not fronts:
        out.append("_No fronts yet._\n")
        return "\n".join(out)

    # Sort: active first, then name
    def _status_rank(s: str) -> int:
        s = (s or "").lower()
        return {"active": 0, "dormant": 1, "resolved": 2, "catastrophic": 3}.get(s, 9)

    fronts_sorted = sorted(fronts, key=lambda f: (_status_rank(f.get("status")), (f.get("name") or "").lower()))
    for f in fronts_sorted:
        name = f.get("name") or "(unnamed front)"
        status = (f.get("status") or "active").title()
        desc = (f.get("description") or "").strip()
        tags = f.get("tags") or []
        out.append(f"## {name}  \n**Status:** {status}" + _fmt_tags(tags) + "\n")
        if desc:
            out.append(desc + "\n")

        clocks = f.get("clocks") or []
        if not clocks:
            out.append("_No clocks on this front._\n")
            continue

        for c in clocks:
            cname = c.get("name") or "(unnamed clock)"
            total = int(c.get("segments_total") or 6)
            filled = int(c.get("segments_filled") or 0)
            hidden = bool(c.get("hidden") or False)
            prog = f"{filled}/{total}"
            bar = "■" * max(0, min(filled, total)) + "□" * max(0, total - max(0, min(filled, total)))
            flags = []
            if hidden:
                flags.append("hidden")
            if c.get("reversible"):
                flags.append("reversible")
            if flags:
                flag_txt = " (" + ", ".join(flags) + ")"
            else:
                flag_txt = ""
            out.append(f"- **{cname}** — `{prog}` {bar}{flag_txt}")
            cdesc = (c.get("description") or "").strip()
            if cdesc:
                out.append(f"  - {cdesc}")
            trig = (c.get("triggers") or "").strip()
            if trig:
                out.append(f"  - **Advances when:** {trig}")
            eff = (c.get("completion_effect") or "").strip()
            if eff:
                out.append(f"  - **On completion:** {eff}")
        out.append("")
    return "\n".join(out).rstrip() + "\n"


def render_chronicle_markdown(state: Dict[str, Any]) -> str:
    """Chronicle log suitable for session notes."""
    session = (state.get("session") or {}).get("count")
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    out: List[str] = []
    out.append(f"# Chronicle Log\n")
    out.append(f"*Generated:* {now}" + (f"  \n*Session:* {session}" if session is not None else "") + "\n")

    log = state.get("chronicle") or []
    if not log:
        out.append("_No chronicle entries yet._\n")
        return "\n".join(out)

    # Newest first by default
    for e in sorted(log, key=lambda x: (x.get("created") or ""), reverse=True):
        created = e.get("created") or ""
        front = e.get("front_name") or e.get("front_id") or ""
        clock = e.get("clock_name") or e.get("clock_id") or ""
        kind = (e.get("kind") or "event").title()
        reason = (e.get("reason") or "").strip()
        delta = e.get("delta")
        seg = e.get("segments")
        sess = e.get("session")
        head = f"## {kind}: {front}"
        if clock:
            head += f" — {clock}"
        out.append(head)
        meta_bits: List[str] = []
        if created:
            meta_bits.append(f"{created}")
        if sess is not None:
            meta_bits.append(f"Session {sess}")
        if delta is not None and seg is not None:
            meta_bits.append(f"Δ {delta} → {seg}")
        if meta_bits:
            out.append("*" + " | ".join(meta_bits) + "*\n")
        if reason:
            out.append(reason + "\n")
        detail = (e.get("detail") or "").strip()
        if detail:
            out.append(detail + "\n")
    return "\n".join(out).rstrip() + "\n"
