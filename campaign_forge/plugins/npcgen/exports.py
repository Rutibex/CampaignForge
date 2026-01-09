from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from .generator import npc_roster_to_markdown


def export_npc_markdown(ctx, roster: Dict[str, Any], *, title: str = "NPC Roster", seed: Optional[int] = None) -> Path:
    """Write an npc.md into a session pack and return the path."""
    pack_dir = ctx.export_manager.create_session_pack("npc_roster", seed=seed)
    md = npc_roster_to_markdown(roster, title=title)
    p = ctx.export_manager.write_markdown(pack_dir, "npc.md", md)
    return p


def export_npc_cards_pdf_placeholder(ctx, roster: Dict[str, Any], *, seed: Optional[int] = None) -> Optional[Path]:
    """Placeholder for a future PDF export.

    We don't create a fake PDF today; we just reserve the API so UI can call it later
    without breaking saved projects.
    """
    return None
