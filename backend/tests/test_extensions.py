from __future__ import annotations

from pathlib import Path

from app.extensions import ExtensionRegistry
from app.core.config import Settings


def test_extension_registry_discovers_only_valid_declarative_manifests(tmp_path: Path) -> None:
    skill = tmp_path / "skills" / "calendar"
    skill.mkdir(parents=True)
    (skill / "manifest.json").write_text('{"name":"calendar","version":"1","description":"Read dates"}', encoding="utf-8")
    (tmp_path / "plugins").mkdir()
    (tmp_path / "mcp").mkdir()
    items = ExtensionRegistry(skills_dir=tmp_path / "skills", plugins_dir=tmp_path / "plugins", mcp_dir=tmp_path / "mcp").list()
    assert items[0]["name"] == "calendar"
    assert items[0]["enabled"] is False and items[0]["executable"] is False


def test_generic_llm_key_overrides_legacy_deepseek_key() -> None:
    settings = Settings(llm_api_key="generic", deepseek_api_key="legacy")
    assert settings.resolved_llm_api_key.get_secret_value() == "generic"
