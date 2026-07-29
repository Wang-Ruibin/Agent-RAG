from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


ToolStatus = Literal["completed", "failed", "timeout", "blocked"]


@dataclass(frozen=True, slots=True)
class ToolCall:
    name: str
    arguments: dict[str, Any]


@dataclass(slots=True)
class ToolEvent:
    index: int
    tool: str
    status: ToolStatus
    summary: str
    duration_ms: int
    result: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class AgentPlan:
    calls: list[ToolCall]
    final_query: str

