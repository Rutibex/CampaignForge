from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Dict, Any, Optional
import json


def export_session_pack(ctx, result: Any, slug: Optional[str] = None) -> Path:
    """
    Writes a full encounter session pack:
      - encounter.md
      - encounter.json
      - statblocks.md (extracted)
    """
    em = ctx.export_manager
    pack_dir = em.create_session_pack("encounter", seed=getattr(result, "seed_used", None), slug=(slug or "encounter"))

    # encounter.md
    md = getattr(result, "markdown", "")
    em.write_markdown(pack_dir, "encounter.md", md)

    # encounter.json
    payload = result
    if hasattr(result, "__dataclass_fields__"):
        payload = asdict(result)
    elif hasattr(result, "to_dict"):
        payload = result.to_dict()

    (pack_dir / "encounter.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")

    # statblocks.md
    try:
        statblocks = payload.get("statblocks") or []
    except Exception:
        statblocks = []

    sb_lines = ["# Stat Blocks", ""]
    for sb in statblocks:
        name = sb.get("name", "Creature")
        sb_lines.append(f"## {name}")
        sb_lines.append(f"*{sb.get('size','Medium')} {sb.get('kind','Creature')}, {sb.get('alignment','unaligned')}*")
        sb_lines.append(f"- **AC** {sb.get('armor_class')}  **HP** {sb.get('hit_points')}  **Speed** {sb.get('speed')}")
        sb_lines.append(f"- **STR** {sb.get('str_')}  **DEX** {sb.get('dex')}  **CON** {sb.get('con')}  **INT** {sb.get('int_')}  **WIS** {sb.get('wis')}  **CHA** {sb.get('cha')}")
        sb_lines.append(f"- **PB** +{sb.get('proficiency_bonus')}  **Atk** +{sb.get('attack_bonus')}  **Save DC** {sb.get('save_dc')}")
        sb_lines.append("")
        sb_lines.append("**Traits**")
        for tr in sb.get("traits") or []:
            sb_lines.append(f"- {tr}")
        sb_lines.append("")
        sb_lines.append("**Actions**")
        for act in sb.get("actions") or []:
            sb_lines.append(f"- {act}")
        sb_lines.append("")
    em.write_markdown(pack_dir, "statblocks.md", "\n".join(sb_lines))

    return pack_dir
