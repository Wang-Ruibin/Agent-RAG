from __future__ import annotations

import time
from contextlib import nullcontext

from app.agent.contracts import AgentPlan, ToolCall
from app.agent.router import ChatMode, route_question
from app.agent.runner import AgentRunner
from app.agent.tools import ToolValidationError


class FakeRegistry:
    def __init__(self, *, sleep_seconds: float = 0) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []
        self.sleep_seconds = sleep_seconds

    def execute(self, name: str, arguments: dict[str, object], _db: object) -> dict[str, object]:
        self.calls.append((name, arguments))
        if self.sleep_seconds:
            time.sleep(self.sleep_seconds)
        if name == "invalid":
            raise ToolValidationError("not allowed")
        return {"items": [{"document_id": 1}], "name": name}


def test_auto_router_uses_rag_for_simple_question() -> None:
    assert route_question("河海大学校训是什么").mode is ChatMode.RAG


def test_auto_router_uses_agent_for_time_sensitive_question() -> None:
    decision = route_question("河海大学今天有什么活动")
    assert decision.mode is ChatMode.AGENT
    assert decision.reason == "multi_step_or_time_sensitive_query"


def test_runner_blocks_duplicate_tool_calls() -> None:
    registry = FakeRegistry()
    runner = AgentRunner(registry=registry, session_factory=lambda: nullcontext(object()))
    result = runner.run(
        "测试",
        object(),
        plan=AgentPlan(
            final_query="测试",
            calls=[
                ToolCall("search_campus_knowledge", {"query": "测试"}),
                ToolCall("search_campus_knowledge", {"query": "测试"}),
            ],
        ),
    )
    assert [event.status for event in result.tool_events] == ["completed", "blocked"]
    assert len(registry.calls) == 1


def test_runner_enforces_per_tool_timeout_without_waiting_for_worker() -> None:
    registry = FakeRegistry(sleep_seconds=0.2)
    runner = AgentRunner(registry=registry, session_factory=lambda: nullcontext(object()))
    runner.tool_timeout_seconds = 0.01
    started = time.monotonic()
    result = runner.run("测试", object())
    elapsed = time.monotonic() - started
    assert result.tool_events[0].status == "timeout"
    assert elapsed < 0.1


def test_runner_rejects_plans_over_tool_budget() -> None:
    runner = AgentRunner(registry=FakeRegistry(), session_factory=lambda: nullcontext(object()))
    plan = AgentPlan(
        final_query="测试",
        calls=[ToolCall("search_campus_knowledge", {"query": str(index)}) for index in range(5)],
    )
    try:
        runner.run("测试", object(), plan=plan)
    except ToolValidationError as exc:
        assert "exceeds" in str(exc)
    else:
        raise AssertionError("expected tool budget validation")
