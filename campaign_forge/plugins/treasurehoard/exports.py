from __future__ import annotations

from pathlib import Path
from typing import Dict, Any, List
import json
import datetime


def _fmt_gp(n: int) -> str:
    return f"{n:,} gp"


def _coins_line(coins: Dict[str, int]) -> str:
    parts = []
    for k in ["pp", "gp", "ep", "sp", "cp"]:
        v = int(coins.get(k, 0))
        if v:
            parts.append(f"{v:,} {k.upper()}")
    return ", ".join(parts) if parts else "—"


def hoard_to_markdown(hoard: Dict[str, Any]) -> str:
    cfg = hoard.get("config", {})
    totals = hoard.get("totals", {})

    title = f"Treasure Hoard — {cfg.get('scale','')}"
    seed = hoard.get("seed", None)

    lines: List[str] = []
    lines.append(f"# {title}")
    lines.append("")
    lines.append(f"- **Seed:** `{seed}`")
    lines.append(f"- **Owner:** {cfg.get('owner_type','')}")
    lines.append(f"- **Intent:** {cfg.get('intent','')}")
    lines.append(f"- **Age:** {cfg.get('age','')}")
    lines.append(f"- **Culture:** {cfg.get('culture','Local')}")
    lines.append(f"- **Magic Density:** {cfg.get('magic_density','Standard')}")
    lines.append("")
    lines.append("## Totals")
    lines.append("")
    lines.append(f"- **Target Value:** {_fmt_gp(int(totals.get('gp_target', 0)))}")
    lines.append(f"- **Estimated Value (generated):** {_fmt_gp(int(totals.get('gp_estimated', 0)))}")
    lines.append(f"- **Coin Count:** {int(totals.get('coin_count', 0)):,}")
    lines.append(f"- **Estimated Weight:** {totals.get('weight_lbs_est', '—')} lb")
    lines.append("")

    # Coins
    coins = hoard.get("coins", {}) or {}
    lines.append("## Coins")
    lines.append("")
    lines.append(_coins_line(coins))
    lines.append("")

    # Containers
    containers = hoard.get("containers", []) or []
    if containers:
        lines.append("## Storage & Containers")
        lines.append("")
        for c in containers:
            name = c.get("name", "Container")
            notes = c.get("notes", "")
            security = c.get("security", "")
            extra = " — ".join([x for x in [security, notes] if x])
            lines.append(f"- **{name}**" + (f": {extra}" if extra else ""))
        lines.append("")

    # Gems
    gems = hoard.get("gems", []) or []
    lines.append("## Gems & Jewels")
    lines.append("")
    if not gems:
        lines.append("—")
    else:
        for g in gems:
            lines.append(f"- **{g.get('name','Gem')}** — {g.get('gp', 0)} gp ({g.get('rarity','common')})")
            if g.get("detail"):
                lines.append(f"  - {g.get('detail')}")
    lines.append("")

    # Art
    art = hoard.get("art", []) or []
    lines.append("## Art Objects")
    lines.append("")
    if not art:
        lines.append("—")
    else:
        for a in art:
            lines.append(f"- **{a.get('name','Art')}** — {a.get('gp', 0)} gp")
            meta = []
            if a.get("culture"):
                meta.append(str(a.get("culture")))
            if a.get("era"):
                meta.append(str(a.get("era")))
            if meta:
                lines.append(f"  - _{', '.join(meta)}_")
            if a.get("detail"):
                lines.append(f"  - {a.get('detail')}")
    lines.append("")

    # Commodities
    comm = hoard.get("commodities", []) or []
    lines.append("## Commodities")
    lines.append("")
    if not comm:
        lines.append("—")
    else:
        for c in comm:
            qty = c.get("qty", 1)
            unit = c.get("unit", "crate")
            lines.append(f"- **{c.get('name','Commodity')}** — {qty} {unit}(s) × {c.get('gp',0)} gp = **{c.get('total_gp',0)} gp**")
            if c.get("detail"):
                lines.append(f"  - {c.get('detail')}")
    lines.append("")

    # Magic Items
    items = hoard.get("magic_items", []) or []
    lines.append("## Magic Items")
    lines.append("")
    if not items:
        lines.append("—")
    else:
        for it in items:
            gp_est = it.get("gp_est", 0)
            tags = it.get("tags", [])
            tag_str = f" _[{', '.join(tags)}]_" if tags else ""
            lines.append(f"- **{it.get('name','Magic Item')}**{tag_str} — est. {gp_est} gp")
            if it.get("effect"):
                lines.append(f"  - {it.get('effect')}")
            if it.get("drawback"):
                lines.append(f"  - **Drawback:** {it.get('drawback')}")
    lines.append("")

    # Scrolls
    scrolls = hoard.get("scrolls", []) or []
    lines.append("## Scrolls & Written Magic")
    lines.append("")
    if not scrolls:
        lines.append("—")
    else:
        for s in scrolls:
            lines.append(f"- **{s.get('name','Scroll')}** — est. {s.get('gp_est',0)} gp")
            if s.get("effect"):
                lines.append(f"  - {s.get('effect')}")
            if s.get("complication"):
                lines.append(f"  - **Complication:** {s.get('complication')}")
    lines.append("")

    # Relics
    relics = hoard.get("relics", []) or []
    lines.append("## Relics & Symbols")
    lines.append("")
    if not relics:
        lines.append("—")
    else:
        for r in relics:
            lines.append(f"- **{r.get('name','Relic')}** — est. {r.get('gp_est',0)} gp")
            if r.get("meaning"):
                lines.append(f"  - {r.get('meaning')}")
            if r.get("danger"):
                lines.append(f"  - **Danger:** {r.get('danger')}")
    lines.append("")

    # Complications + hooks
    complications = hoard.get("complications", []) or []
    hooks = hoard.get("hooks", []) or []
    if complications or hooks:
        lines.append("## Complications & Hooks")
        lines.append("")
        for c in complications:
            lines.append(f"- **{c.get('title','Complication')}** — {c.get('detail','')}")
        for h in hooks:
            lines.append(f"- {h}")
        lines.append("")

    lines.append("---")
    lines.append(f"_Generated {datetime.datetime.now().isoformat(timespec='seconds')}_")
    return "\n".join(lines)


def hoard_to_json_bytes(hoard: Dict[str, Any]) -> bytes:
    return json.dumps(hoard, indent=2, ensure_ascii=False).encode("utf-8")


def write_session_pack(ctx, hoard: Dict[str, Any], *, title: str = "treasure_hoard") -> Path:
    seed = hoard.get("seed", None)
    pack_dir = ctx.export_manager.create_session_pack(title, seed=seed)
    md = hoard_to_markdown(hoard)
    ctx.export_manager.write_markdown(pack_dir, "hoard.md", md)
    (pack_dir / "hoard.json").write_bytes(hoard_to_json_bytes(hoard))
    return pack_dir
