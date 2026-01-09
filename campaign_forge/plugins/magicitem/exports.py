from __future__ import annotations

from pathlib import Path
from typing import Optional

from .generator import MagicItem


def _safe_slug(text: str) -> str:
    # Simple slugging (no external deps)
    keep = []
    for ch in text.lower():
        if ch.isalnum():
            keep.append(ch)
        elif ch in (" ", "-", "_"):
            keep.append("-")
    slug = "".join(keep)
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug.strip("-")[:60] or "magic-item"


def export_magic_item(ctx, item: MagicItem, *, as_session_pack: bool = True) -> Path:
    """
    Writes export artifacts for the item.
    Preferred: session pack folder containing item.md + item.txt + item.json
    Fallback: ctx.export_path(...) if export_manager isn't present.
    """
    slug = _safe_slug(item.name)

    pack_dir: Optional[Path] = None

    if as_session_pack and getattr(ctx, "export_manager", None) is not None:
        em = ctx.export_manager
        try:
            # expected pattern in your app: create_session_pack(module_id, seed=seed)
            pack_dir = em.create_session_pack("magicitem", seed=item.seed)
        except Exception:
            pack_dir = None

    if pack_dir is None:
        # Fallback: build under exports/ with something stable
        try:
            base = ctx.export_path("magicitem")
        except Exception:
            # Last resort: project_root/exports/magicitem
            base = Path(getattr(ctx, "project_root", ".")) / "exports" / "magicitem"
        base.mkdir(parents=True, exist_ok=True)
        pack_dir = base / f"{slug}_seed{item.seed}"
        pack_dir.mkdir(parents=True, exist_ok=True)

    md_path = pack_dir / "item.md"
    txt_path = pack_dir / "item.txt"
    json_path = pack_dir / "item.json"

    md_path.write_text(item.to_markdown(), encoding="utf-8")
    txt_path.write_text(item.to_markdown(), encoding="utf-8")  # plain text is fine as md
    json_path.write_text(__import__("json").dumps(item.to_dict(), indent=2), encoding="utf-8")

    return pack_dir
