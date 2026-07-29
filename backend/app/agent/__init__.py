"""Safe, auditable agent primitives for CampusQA.

The agent package is intentionally independent from third-party bot projects.
It exposes only structured tool events and never stores or emits model reasoning.
"""

from .router import ChatMode, RouteDecision, route_question
from .runner import AgentRunResult, AgentRunner

__all__ = ("AgentRunResult", "AgentRunner", "ChatMode", "RouteDecision", "route_question")
