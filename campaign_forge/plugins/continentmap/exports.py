from __future__ import annotations

from typing import Dict, Any
from pathlib import Path
from PySide6.QtCore import QBuffer, QByteArray, QIODevice
from PySide6.QtGui import QImage

from .generator import ContinentModel, biome_name


def qimage_to_png_bytes(img: QImage) -> bytes:
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    img.save(buf, "PNG")
    buf.close()
    return bytes(ba)

def build_gazetteer_markdown(model: ContinentModel) -> str:
    lines = []
    lines.append(f"# Continent Gazetteer")
    lines.append("")
    lines.append(f"- **Seed:** `{model.seed}`")
    lines.append(f"- **Size:** `{model.w}×{model.h}` cells")
    lines.append(f"- **Land Coverage:** `{model.notes.get('land_pct', 0.0)*100:.1f}%`")
    lines.append("")
    lines.append("## Factions")
    lines.append("")
    if not model.factions:
        lines.append("_None generated._")
    else:
        for f in model.factions:
            x, y = f.capital
            lines.append(f"### {f.name} ({f.kind})")
            lines.append(f"- Capital: ({x}, {y})")
            lines.append(f"- Color: RGB{f.color}")
            lines.append("")
    lines.append("## Biomes (Counts)")
    lines.append("")
    bc = model.notes.get("biome_counts", {})
    for k, v in bc.items():
        lines.append(f"- {k}: {v}")
    lines.append("")
    lines.append("## GM Hooks (Auto)")
    lines.append("")
    lines.append("- Borderlands (contested tiles) are good places for forts, bandit kings, refugee roads, and proxy wars.")
    lines.append("- Rivers are instant ‘civilization lines’: put cities where rivers meet coasts or join.")
    lines.append("- Mountains + taiga edges make excellent ‘old empire’ ruin belts.")
    lines.append("")
    return "\n".join(lines)


def export_session_pack(ctx, model: ContinentModel, images: Dict[str, QImage]) -> Path:
    pack = ctx.export_manager.create_session_pack("continentmap", seed=model.seed)

    assets: Dict[str, bytes] = {}
    for name, img in images.items():
        assets[name] = qimage_to_png_bytes(img)

    ctx.export_manager.write_assets(pack, assets)
    md = build_gazetteer_markdown(model)
    ctx.export_manager.write_markdown(pack, "gazetteer.md", md)

    # Lightweight JSON snapshot (not the huge arrays; just settings + factions)
    snapshot = {
        "version": 1,
        "seed": model.seed,
        "size": [model.w, model.h],
        "factions": [
            {"id": f.fid, "name": f.name, "kind": f.kind, "capital": list(f.capital), "color": list(f.color)}
            for f in model.factions
        ],
        "notes": model.notes,
    }
    (pack / "summary.json").write_text(__import__("json").dumps(snapshot, indent=2), encoding="utf-8")

    return pack
