from __future__ import annotations

from fastapi import APIRouter

from app.agent.tools import tool_registry
from app.core.config import settings
from app.extensions import ExtensionRegistry

from .dependencies import AdminUser

router = APIRouter(prefix="/api/admin/extensions", tags=["extensions"])


@router.get("")
def list_extensions(_user: AdminUser) -> dict[str, object]:
    registry = ExtensionRegistry(skills_dir=settings.agent_skills_dir, plugins_dir=settings.agent_plugins_dir, mcp_dir=settings.agent_mcp_dir)
    return {
        "extensions": registry.list(),
        "agent_tools": list(tool_registry.names()),
        "sandbox": {"enabled": settings.agent_sandbox_enabled, "execution": "disabled" if not settings.agent_sandbox_enabled else "not implemented"},
    }
