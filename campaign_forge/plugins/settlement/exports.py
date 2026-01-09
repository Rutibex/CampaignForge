
from __future__ import annotations

from pathlib import Path
from typing import List

from PySide6.QtCore import QByteArray, QSize
from PySide6.QtGui import QImage, QPainter

from PySide6.QtSvg import QSvgRenderer

from .generator import Settlement
from .map_render import MapRenderOptions, scene_to_svg


def export_svg(path: Path, settlement: Settlement, opts: MapRenderOptions) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    svg = scene_to_svg(settlement, opts)
    path.write_text(svg, encoding="utf-8")


def export_png(path: Path, settlement: Settlement, opts: MapRenderOptions, *, scale: float = 1.0) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    svg = scene_to_svg(settlement, opts)
    data = QByteArray(svg.encode("utf-8"))
    renderer = QSvgRenderer(data)

    w = int(settlement.map_width * scale)
    h = int(settlement.map_height * scale)
    img = QImage(w, h, QImage.Format_ARGB32)
    img.fill(0x00FFFFFF)

    painter = QPainter(img)
    renderer.render(painter)
    painter.end()

    img.save(str(path))


def export_markdown_key(path: Path, settlement: Settlement) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: List[str] = []
    lines.append(f"# {settlement.name} — {settlement.settlement_type}")
    lines.append("")
    lines.append(f"*Terrain:* **{settlement.terrain}**")
    lines.append(f"*Population:* **{settlement.population_band}**")
    lines.append(f"*Age:* **{settlement.age}**")
    if settlement.tags:
        lines.append(f"*Tags:* {', '.join(settlement.tags)}")
    lines.append("")
    lines.append("## Factions")
    for f in settlement.factions:
        lines.append(f"### {f.name} ({f.kind})")
        lines.append(f"- Goal: {f.goal}")
        lines.append(f"- Method: {f.method}")
        lines.append(f"- Signature: {f.signature}")
        lines.append("")
    lines.append("## Districts")
    for d in settlement.districts:
        lines.append(f"### {d.name}")
        lines.append(f"- Kind: {d.kind}")
        lines.append(f"- Wealth: {d.wealth} | Law: {d.law} | Danger: {d.danger}")
        if d.influence:
            inf = ", ".join([f"{k}:{v}%" for k, v in sorted(d.influence.items(), key=lambda kv: -kv[1])])
            lines.append(f"- Influence: {inf}")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def export_markdown_locations(path: Path, settlement: Settlement) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: List[str] = []
    lines.append(f"# {settlement.name} — Locations")
    lines.append("")
    for d in settlement.districts:
        lines.append(f"## {d.name}")
        lines.append(f"*{d.kind} — Wealth {d.wealth}, Law {d.law}, Danger {d.danger}*")
        lines.append("")
        for loc in d.locations:
            lines.append(f"### {loc.name} ({loc.kind})")
            lines.append(f"- Owner: {loc.owner}")
            lines.append(f"- Hook: {loc.hook}")
            lines.append(f"- Secret: {loc.secret}")
            lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def export_markdown_rumors(path: Path, settlement: Settlement) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: List[str] = []
    lines.append(f"# {settlement.name} — Rumors & Trouble")
    lines.append("")
    lines.append("## Problems")
    for p in settlement.problems:
        lines.append(f"- {p}")
    lines.append("")
    lines.append("## Rumors (True)")
    for r in settlement.rumors_true:
        lines.append(f"- {r}")
    lines.append("")
    lines.append("## Rumors (Half-True)")
    for r in settlement.rumors_half:
        lines.append(f"- {r}")
    lines.append("")
    lines.append("## Rumors (False)")
    for r in settlement.rumors_false:
        lines.append(f"- {r}")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
