from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from dataclasses import dataclass, field
from typing import Any, Callable

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal

from .contracts import AgentPlan, ToolCall, ToolEvent
from .tools import ToolValidationError, tool_registry


@dataclass(slots=True)
class AgentRunResult:
    final_query: str
    tool_events: list[ToolEvent] = field(default_factory=list)
    evidence: list[dict[str, Any]] = field(default_factory=list)


class AgentRunner:
    """Bounded sequential executor for a deliberately small read-only tool surface."""

    max_tool_calls = 4
    max_llm_rounds = 5
    tool_timeout_seconds = 8.0
    total_timeout_seconds = 45.0
    max_tool_result_chars = 12_000

    def __init__(
        self,
        registry=tool_registry,  # type: ignore[no-untyped-def]
        session_factory=SessionLocal,  # type: ignore[no-untyped-def]
    ) -> None:
        self.registry = registry
        self.session_factory = session_factory
        self.max_tool_calls = settings.agent_max_tool_calls
        self.max_llm_rounds = settings.agent_max_llm_rounds
        self.tool_timeout_seconds = settings.agent_tool_timeout_seconds
        self.total_timeout_seconds = settings.agent_total_timeout_seconds
        self.max_tool_result_chars = settings.agent_tool_result_max_chars

    @staticmethod
    def default_plan(question: str) -> AgentPlan:
        normalized = question.lower()
        policy_terms = ("\u653f\u7b56", "\u89c4\u5b9a", "\u529e\u6cd5", "\u5bf9\u6bd4", "\u6bd4\u8f83", "compare", "policy")
        tool_name = "compare_policies" if any(term in normalized for term in policy_terms) else "search_campus_knowledge"
        calls = [ToolCall(tool_name, {"query": question, "top_k": 5})]
        current_terms = ("\u4eca\u5929", "\u5f53\u524d", "\u73b0\u5728", "\u6700\u65b0", "\u622a\u81f3", "today", "current", "latest")
        if any(term in normalized for term in current_terms):
            calls.insert(0, ToolCall("get_current_date", {}))
        return AgentPlan(calls=calls, final_query=question)
        calls = [ToolCall("search_campus_knowledge", {"query": question, "top_k": 5})]
        if any(token in question for token in ("今天", "当前", "现在", "最新", "截至")):
            calls.insert(0, ToolCall("get_current_date", {}))
        return AgentPlan(calls=calls, final_query=question)

    def run(
        self,
        question: str,
        db: Session,
        *,
        plan: AgentPlan | None = None,
        on_event: Callable[[ToolEvent], None] | None = None,
    ) -> AgentRunResult:
        plan = plan or self.default_plan(question)
        if len(plan.calls) > self.max_tool_calls:
            raise ToolValidationError(f"agent plan exceeds {self.max_tool_calls} tool calls")
        started = time.monotonic()
        seen: set[str] = set()
        run = AgentRunResult(final_query=plan.final_query)

        for index, call in enumerate(plan.calls, start=1):
            elapsed = time.monotonic() - started
            if elapsed >= self.total_timeout_seconds:
                event = ToolEvent(index, call.name, "timeout", "agent time budget exhausted", 0)
                run.tool_events.append(event)
                if on_event:
                    on_event(event)
                break
            fingerprint = f"{call.name}:{json.dumps(call.arguments, sort_keys=True, ensure_ascii=False)}"
            if fingerprint in seen:
                event = ToolEvent(index, call.name, "blocked", "duplicate tool call blocked", 0)
                run.tool_events.append(event)
                if on_event:
                    on_event(event)
                continue
            seen.add(fingerprint)
            # A request session is thread-confined.  Each bounded tool gets its
            # own read-only session inside the worker that enforces the timeout.
            event = self._execute(index, call, self.total_timeout_seconds - elapsed)
            run.tool_events.append(event)
            if on_event:
                on_event(event)
            if call.name in {"search_campus_knowledge", "retrieve_document_evidence", "compare_policies"}:
                run.evidence.extend(event.result.get("items", []))
        return run

    def _execute(self, index: int, call: ToolCall, remaining: float) -> ToolEvent:
        started = time.monotonic()
        timeout = max(0.01, min(self.tool_timeout_seconds, remaining))
        def execute_in_read_session() -> dict[str, Any]:
            with self.session_factory() as tool_db:
                return self.registry.execute(call.name, call.arguments, tool_db)

        pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="agent-tool")
        future = pool.submit(execute_in_read_session)
        try:
            result = future.result(timeout=timeout)
            encoded = json.dumps(result, ensure_ascii=False)
            if len(encoded) > self.max_tool_result_chars:
                result = {"truncated": True, "preview": encoded[: self.max_tool_result_chars]}
            duration = int((time.monotonic() - started) * 1000)
            item_count = len(result.get("items", [])) if isinstance(result, dict) else 0
            return ToolEvent(index, call.name, "completed", f"completed ({item_count} evidence items)", duration, result)
        except TimeoutError:
            future.cancel()
            return ToolEvent(index, call.name, "timeout", "tool timed out", int((time.monotonic() - started) * 1000))
        except ToolValidationError as exc:
            return ToolEvent(index, call.name, "blocked", str(exc), int((time.monotonic() - started) * 1000))
        except Exception:
            return ToolEvent(index, call.name, "failed", "tool execution failed", int((time.monotonic() - started) * 1000))
        finally:
            # Do not wait for a timed-out third-party/network operation.  Built-in
            # tools are read-only; a future sandbox process boundary will provide
            # hard cancellation for any privileged extensions.
            pool.shutdown(wait=False, cancel_futures=True)


agent_runner = AgentRunner()
