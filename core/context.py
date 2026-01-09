from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import hashlib
import json
import random
from typing import Any, Callable, Dict, Optional, Sequence

from .export_manager import ExportManager


def _stable_int_from_parts(parts: Sequence[Any]) -> int:
    h = hashlib.sha256()
    for p in parts:
        h.update(str(p).encode("utf-8"))
        h.update(b"\x1f")
    # random.Random accepts up to 2**32-1 nicely, keep it compact
    return int.from_bytes(h.digest()[:4], "big")


@dataclass
class ForgeContext:
    """Shared context passed to plugins.

    This is the place for shared services (project, settings, exports, persistence, scratchpad).
    """

    project_dir: Path = field(default_factory=lambda: Path.cwd() / "projects" / "default_project")
    rng: random.Random = field(default_factory=lambda: random.Random(1337))
    log: Callable[[str], None] = print

    # Services (wired by MainWindow)
    scratchpad_add: Callable[[str, Optional[Sequence[str]]], None] = lambda _text, _tags=None: None

    # Project-level settings (persisted in project_dir/project.json)
    project_settings: Dict[str, Any] = field(default_factory=dict)

    def set_project_dir(self, new_dir: Path) -> None:
        self.project_dir = Path(new_dir)
        self.ensure_project_dirs()
        self.load_project_settings()
        self._reset_rng_from_project_seed()

    # ---------- dirs / settings ----------

    def ensure_project_dirs(self) -> None:
        (self.project_dir / "exports").mkdir(parents=True, exist_ok=True)
        (self.project_dir / "modules").mkdir(parents=True, exist_ok=True)
        (self.project_dir / "logs").mkdir(parents=True, exist_ok=True)
        (self.project_dir / "themes").mkdir(parents=True, exist_ok=True)
        (self.project_dir / "packs").mkdir(parents=True, exist_ok=True)

    @property
    def asset_dir(self) -> Path:
        # Reserved for future shared assets; packs/themes live alongside.
        p = self.project_dir / "assets"
        p.mkdir(parents=True, exist_ok=True)
        return p

    def load_project_settings(self) -> None:
        p = self.project_dir / "project.json"
        if p.exists():
            try:
                self.project_settings = json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                self.project_settings = {}
        else:
            self.project_settings = {}

        # Defaults
        self.project_settings.setdefault("name", self.project_dir.name)
        self.project_settings.setdefault("master_seed", 1337)
        self.project_settings.setdefault("export_subdir", "")  # optional extra folder inside exports

    def save_project_settings(self) -> None:
        p = self.project_dir / "project.json"
        p.write_text(json.dumps(self.project_settings, indent=2, ensure_ascii=False), encoding="utf-8")

    # ---------- RNG / reproducibility ----------

    @property
    def master_seed(self) -> int:
        try:
            return int(self.project_settings.get("master_seed", 1337))
        except Exception:
            return 1337

    def _reset_rng_from_project_seed(self) -> None:
        self.rng = random.Random(self.master_seed)

    def derive_seed(self, *parts: Any) -> int:
        """Derive a deterministic sub-seed from the project seed + arbitrary parts."""
        return _stable_int_from_parts((self.master_seed, *parts))

    def derive_rng(self, *parts: Any) -> random.Random:
        return random.Random(self.derive_seed(*parts))

    # ---------- file helpers ----------

    def save_json(self, relpath: str, data: Any) -> None:
        p = (self.project_dir / relpath).resolve()
        if self.project_dir not in p.parents and p != self.project_dir:
            raise ValueError("Refusing to write outside the project directory.")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def load_json(self, relpath: str, default: Any = None) -> Any:
        p = (self.project_dir / relpath)
        if not p.exists():
            return default
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return default

    # ---------- exports ----------

    @property
    def export_manager(self) -> ExportManager:
        return ExportManager(self.project_dir)

    def export_path(self, name: str, ext: str, *, timestamp: bool = True, seed: Optional[int] = None, subdir: Optional[str] = None) -> Path:
        # allow project to tack on an extra layer under exports/
        export_subdir = str(self.project_settings.get("export_subdir", "") or "").strip()
        if export_subdir:
            subdir = f"{export_subdir}/{subdir}" if subdir else export_subdir
        return self.export_manager.export_path(name, ext, timestamp=timestamp, seed=seed, subdir=subdir)
