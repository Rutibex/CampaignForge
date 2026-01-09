from __future__ import annotations

from pathlib import Path
from typing import Dict, Any, Optional, Tuple

from .generator import artifact_to_markdown

def export_session_pack(ctx, artifact: Dict[str, Any], slug: Optional[str] = None) -> Path:
    """
    Creates a session pack folder and writes:
      - artifact_gm.md
      - artifact_player.md
      - artifact.json
    Returns pack_dir.
    """
    name = artifact.get("name", "artifact")
    pack_dir = ctx.export_manager.create_session_pack("artifacts", slug=slug or name, seed=(artifact.get('_provenance',{}) or {}).get('seed'))
    # Markdown
    gm_md = artifact_to_markdown(artifact, for_players=False)
    pl_md = artifact_to_markdown(artifact, for_players=True)

    ctx.export_manager.write_markdown(pack_dir, "artifact_gm.md", gm_md)
    ctx.export_manager.write_markdown(pack_dir, "artifact_player_handout.md", pl_md)

    # JSON
    import json
    (pack_dir / "artifact.json").write_text(json.dumps(artifact, indent=2, ensure_ascii=False), encoding="utf-8")

    # Quick index
    index = f"# Session Pack: {name}\n\n- artifact_gm.md\n- artifact_player_handout.md\n- artifact.json\n"
    ctx.export_manager.write_markdown(pack_dir, "README.md", index)

    return pack_dir
