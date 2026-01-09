from __future__ import annotations

from pathlib import Path
from typing import Dict

from campaign_forge.core.context import ForgeContext
from .generator import LocationStack, stack_to_markdown, stack_to_json, dungeon_svg_bytes
import json


def export_session_pack(ctx: ForgeContext, stack: LocationStack, *, title: str = "location_stack") -> Dict[str, Path]:
    pack_dir = ctx.export_manager.create_session_pack(title, seed=stack.seed or None)

    written: Dict[str, Path] = {}

    md = stack_to_markdown(stack)
    written["markdown"] = ctx.export_manager.write_markdown(pack_dir, "location_stack.md", md)

    json_path = pack_dir / "location_stack.json"
    json_path.write_text(json.dumps(stack_to_json(stack), indent=2, ensure_ascii=False), encoding="utf-8")
    written["json"] = json_path

    svg = dungeon_svg_bytes(stack, cell_size=10)
    if svg:
        svg_path = pack_dir / "dungeon.svg"
        svg_path.write_bytes(svg)
        written["dungeon_svg"] = svg_path

    return written
