# campaign_forge/plugins/potions/exports.py

from __future__ import annotations

from pathlib import Path
from typing import List, Dict, Any
from .generator import Potion, potion_to_markdown_card, potion_to_json


def export_potion_session_pack(ctx, potions: List[Potion], *, slug: str, seed: int) -> Path:
    """
    Writes a session pack folder with:
      - potions.md (all)
      - cards/ potion_###.md
      - potions.json
    """
    pack_dir = ctx.export_manager.create_session_pack("potions", seed=seed, slug=slug)
    cards_dir = Path(pack_dir) / "cards"
    cards_dir.mkdir(parents=True, exist_ok=True)

    # Full markdown
    all_md = []
    all_md.append("# Potion Drop\n")
    all_md.append(f"- Seed: `{seed}`\n")
    all_md.append(f"- Count: `{len(potions)}`\n")
    all_md.append("\n---\n")
    for i, p in enumerate(potions, start=1):
        all_md.append(p.rules_text_md)
        all_md.append("\n---\n")
        card = potion_to_markdown_card(p)
        (cards_dir / f"potion_{i:03d}.md").write_text(card, encoding="utf-8")

    (Path(pack_dir) / "potions.md").write_text("\n".join(all_md), encoding="utf-8")

    # JSON bundle
    json_list = [p.to_jsonable() for p in potions]
    import json
    (Path(pack_dir) / "potions.json").write_text(json.dumps(json_list, indent=2, ensure_ascii=False), encoding="utf-8")

    return Path(pack_dir)
