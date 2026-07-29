from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ChatMode(StrEnum):
    AUTO = "auto"
    RAG = "rag"
    AGENT = "agent"


@dataclass(frozen=True, slots=True)
class RouteDecision:
    mode: ChatMode
    reason: str


# Deliberately small and explainable.  Routing must never depend on hidden model
# reasoning because it controls whether tools are allowed to run.
_AGENT_SIGNALS = (
    "比较",
    "对比",
    "分别",
    "先",
    "再",
    "然后",
    "计划",
    "步骤",
    "今天",
    "当前",
    "现在",
    "最新",
    "截至",
    "汇总",
    "结合",
    "多个",
    "两者",
)


def route_question(question: str, requested_mode: ChatMode | str = ChatMode.AUTO) -> RouteDecision:
    """Select a deterministic chat path without interpreting user content as instructions."""
    mode = ChatMode(requested_mode)
    if mode is ChatMode.RAG:
        return RouteDecision(mode, "user_selected_rag")
    if mode is ChatMode.AGENT:
        return RouteDecision(mode, "user_selected_agent")

    normalized = question.strip().lower()
    if any(signal in normalized for signal in _AGENT_SIGNALS):
        return RouteDecision(ChatMode.AGENT, "multi_step_or_time_sensitive_query")
    return RouteDecision(ChatMode.RAG, "single_hop_knowledge_query")
