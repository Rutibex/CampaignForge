from __future__ import annotations

from pathlib import Path
from typing import Dict, Any, Tuple, List
import json

from PySide6.QtGui import QImage
from PySide6.QtCore import QByteArray, QBuffer, QIODevice


def qimage_to_png_bytes(img: QImage) -> bytes:
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QIODevice.WriteOnly)
    img.save(buf, "PNG")
    buf.close()
    return bytes(ba)


def save_png(img: QImage, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(path), "PNG")


def save_json(data: Dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def build_atlas_markdown(world: Dict[str, Any]) -> str:
    """
    world: dict shape returned by PlanetGenWidget.build_atlas_payload()
    """
    lines: List[str] = []
    lines.append(f"# Planet Atlas — {world.get('title','Unnamed World')}")
    lines.append("")
    lines.append("## Parameters")
    for k,v in world.get("params", {}).items():
        lines.append(f"- **{k}**: {v}")
    lines.append("")
    lines.append("## Factions")
    for f in world.get("factions", []):
        lines.append(f"### {f.get('name','Faction')}")
        lines.append(f"- Style: {f.get('style','')}")
        tags = ", ".join(f.get("tags", []) or [])
        if tags:
            lines.append(f"- Tags: {tags}")
        motives = f.get("motives", []) or []
        if motives:
            lines.append("- Motives:")
            for m in motives:
                lines.append(f"  - {m}")
        lines.append("")

    lines.append("## Settlements")
    for s in world.get("settlements", []):
        lines.append(f"- **{s.get('name','Settlement')}** ({s.get('kind','')}) — ({s.get('x')},{s.get('y')})"
                     + (f" — Faction {s.get('faction')}" if s.get('faction') is not None else ""))
    lines.append("")

    lines.append("## Points of Interest")
    for p in world.get("pois", []):
        lines.append(f"- **{p.get('name','POI')}** — *{p.get('category','')}* — ({p.get('x')},{p.get('y')})"
                     + (f" — {p.get('biome','')}" if p.get('biome') else ""))
    lines.append("")
    return "\n".join(lines)
