from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

ExtensionKind = Literal["skill", "plugin", "mcp"]


@dataclass(frozen=True, slots=True)
class ExtensionManifest:
    kind: ExtensionKind
    name: str
    version: str
    description: str
    path: str
    enabled: bool = False
    executable: bool = False


class ExtensionRegistry:
    """Discovers declarative extension manifests without loading their code."""

    def __init__(self, *, skills_dir: Path, plugins_dir: Path, mcp_dir: Path) -> None:
        self.skills_dir, self.plugins_dir, self.mcp_dir = skills_dir, plugins_dir, mcp_dir

    def list(self) -> list[dict[str, object]]:
        entries = [*self._discover("skill", self.skills_dir), *self._discover("plugin", self.plugins_dir), *self._discover("mcp", self.mcp_dir)]
        return [asdict(item) for item in sorted(entries, key=lambda item: (item.kind, item.name))]

    @staticmethod
    def _discover(kind: ExtensionKind, directory: Path) -> list[ExtensionManifest]:
        if not directory.is_dir():
            return []
        result: list[ExtensionManifest] = []
        for path in sorted(directory.glob("*/manifest.json")):
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(raw, dict):
                continue
            name, version, description = raw.get("name"), raw.get("version", "0"), raw.get("description", "")
            if not isinstance(name, str) or not name or not isinstance(version, str) or not isinstance(description, str):
                continue
            result.append(ExtensionManifest(kind, name[:120], version[:80], description[:500], str(path.parent)))
        return result
