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


_AGENT_SIGNALS = _AGENT_SIGNALS + (
    "\u6bd4\u8f83", "\u5bf9\u6bd4", "\u5206\u522b", "\u4ea4\u66ff", "\u7136\u540e", "\u8ba1\u5212", "\u6b65\u9aa4",
    "\u4eca\u5929", "\u5f53\u524d", "\u73b0\u5728", "\u6700\u65b0", "\u622a\u81f3", "\u6c47\u603b", "\u7ed3\u5408",
    "\u591a\u4e2a", "\u4e24\u8005", "compare", "plan", "latest", "current",
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
