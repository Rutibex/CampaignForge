from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QSettings


@dataclass
class AppSettings:
    """Thin wrapper around QSettings for Campaign Forge app-wide prefs."""

    org: str = "CampaignForge"
    app: str = "Campaign Forge"

    def __post_init__(self) -> None:
        self._qs = QSettings(self.org, self.app)

    def get_last_project_dir(self) -> Optional[Path]:
        v = self._qs.value("last_project_dir", "")
        v = str(v) if v is not None else ""
        v = v.strip()
        return Path(v) if v else None

    def set_last_project_dir(self, path: Path) -> None:
        self._qs.setValue("last_project_dir", str(Path(path)))

    def get_window_geometry(self) -> Optional[bytes]:
        v = self._qs.value("window_geometry", None)
        return v if isinstance(v, (bytes, bytearray)) else None

    def set_window_geometry(self, geometry: bytes) -> None:
        self._qs.setValue("window_geometry", geometry)
