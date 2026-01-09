from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional
import json

from .generator import AdventureSeed, seed_to_markdown


def export_seed_session_pack(ctx, seed: AdventureSeed, *, title: Optional[str] = None) -> Path:
    """
    Writes a session pack containing:
      - seed.md (full summary)
      - components.md (hook/location/antagonist/twist/clock)
      - seed.json (machine-readable)
    Returns the pack directory Path.
    """
    title = title or (seed.location.data.get("name") if seed and seed.location and seed.location.data else None) or "adventure_seed"
    pack_dir = ctx.export_manager.create_session_pack(str(title), seed=int(seed.derived_seed))

    md = seed_to_markdown(seed)
    ctx.export_manager.write_markdown(pack_dir, "seed.md", md)

    # JSON export
    (pack_dir / "seed.json").write_text(json.dumps(seed.to_jsonable(), indent=2), encoding="utf-8")

    return pack_dir
