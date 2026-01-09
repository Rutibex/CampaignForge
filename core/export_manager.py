from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Tuple
import re
import time


def _slug(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"[^a-z0-9\-_ ]+", "", s)
    s = re.sub(r"\s+", "-", s)
    return s[:60] or "session"


@dataclass
class ExportManager:
    project_dir: Path

    def export_root(self) -> Path:
        p = self.project_dir / "exports"
        p.mkdir(parents=True, exist_ok=True)
        return p

    def make_filename(self, stem: str, ext: str, *, timestamp: bool = True, seed: Optional[int] = None) -> str:
        ext = ext.lstrip(".")
        parts = []
        if timestamp:
            parts.append(time.strftime("%Y%m%d_%H%M%S"))
        parts.append(_slug(stem))
        if seed is not None:
            parts.append(f"seed{seed}")
        name = "_".join([p for p in parts if p])
        return f"{name}.{ext}"

    def export_path(self, stem: str, ext: str, *, timestamp: bool = True, seed: Optional[int] = None, subdir: Optional[str] = None) -> Path:
        root = self.export_root()
        if subdir:
            root = root / subdir
            root.mkdir(parents=True, exist_ok=True)
        return root / self.make_filename(stem, ext, timestamp=timestamp, seed=seed)

    def create_session_pack(self, title: str, *, seed: Optional[int] = None) -> Path:
        ts = time.strftime("%Y%m%d_%H%M%S")
        folder = f"{ts}_{_slug(title)}" + (f"_seed{seed}" if seed is not None else "")
        path = self.export_root() / "session_packs" / folder
        path.mkdir(parents=True, exist_ok=True)
        return path

    def write_markdown(self, pack_dir: Path, filename: str, content: str) -> Path:
        if not filename.lower().endswith(".md"):
            filename += ".md"
        p = pack_dir / filename
        p.write_text(content, encoding="utf-8")
        return p

    def write_assets(self, pack_dir: Path, assets: Dict[str, bytes]) -> Dict[str, Path]:
        out: Dict[str, Path] = {}
        for rel, data in assets.items():
            rel = rel.lstrip("/\\")
            p = pack_dir / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data)
            out[rel] = p
        return out
