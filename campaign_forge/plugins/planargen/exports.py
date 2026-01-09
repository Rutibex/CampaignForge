# =========================
# campaign_forge/plugins/planargen/exports.py
# =========================
from __future__ import annotations

from pathlib import Path
from typing import Optional

from .generator import PlaneProfile, plane_to_markdown


def export_plane_markdown(ctx, plane: PlaneProfile, slug: Optional[str] = None) -> Path:
    """
    Export to a session pack if ctx.export_manager supports it, otherwise to exports/planargen/.
    """
    safe_slug = slug or _slugify(plane.name)
    fname = f"plane_{safe_slug}.md"

    # Try session pack convention if available
    pack_dir = None
    if hasattr(ctx, "export_manager") and hasattr(ctx.export_manager, "create_session_pack"):
        try:
            pack_dir = ctx.export_manager.create_session_pack("planargen", seed=plane.seed)
        except Exception as e:
            ctx.log(f"[PlanarGen] ExportManager session pack failed, using fallback. ({e})")

    if pack_dir is None:
        # Fallback: ctx.export_path("exports/...", ensure dirs exist)
        # ADAPT_HERE: if your ctx.export_path signature differs.
        try:
            base = ctx.export_path("planargen")  # might return exports/planargen
        except Exception:
            # final fallback: write into project_root/exports/planargen
            base = Path(ctx.project_root) / "exports" / "planargen"
        base.mkdir(parents=True, exist_ok=True)
        out_path = base / fname
    else:
        out_path = Path(pack_dir) / fname

    out_path.write_text(plane_to_markdown(plane), encoding="utf-8")
    return out_path


def _slugify(s: str) -> str:
    s = s.strip().lower()
    out = []
    for ch in s:
        if ch.isalnum():
            out.append(ch)
        elif ch in (" ", "-", "_"):
            out.append("_")
    slug = "".join(out)
    while "__" in slug:
        slug = slug.replace("__", "_")
    return slug.strip("_")[:60] or "plane"
