from __future__ import annotations

from pathlib import Path
from typing import Optional
from .generator import TrapResult


def export_trap_markdown(ctx, trap: TrapResult, slug: Optional[str] = None) -> Path:
    """
    Writes a single Markdown file. Prefer session pack when available.
    Returns the written path.
    """
    safe_slug = slug or trap.title.lower().replace(" ", "_").replace(":", "").replace("/", "-")
    content = trap.to_markdown()

    # Prefer ExportManager session pack if present
    pack_dir = None
    if hasattr(ctx, "export_manager") and getattr(ctx.export_manager, "create_session_pack", None):
        try:
            pack_dir = ctx.export_manager.create_session_pack("trickstrap", seed=trap.seed_used)
        except Exception as e:
            ctx.log(f"[Tricks&Traps] ExportManager create_session_pack failed, falling back. {e}")

    if pack_dir:
        out_path = Path(pack_dir) / f"trap_{safe_slug}.md"
    else:
        # fallback: ctx.export_path if available, else exports/ in project root
        if hasattr(ctx, "export_path"):
            out_path = Path(ctx.export_path(f"trap_{safe_slug}.md"))
        else:
            out_path = Path(ctx.project_root) / "exports" / f"trap_{safe_slug}.md"
            out_path.parent.mkdir(parents=True, exist_ok=True)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(content, encoding="utf-8")
    return out_path
