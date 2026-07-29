from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import TYPE_CHECKING, Any, Callable
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.orm import Document
if TYPE_CHECKING:
    from app.rag.retrieval import RetrievalResult


class ToolValidationError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ToolDefinition:
    name: str
    description: str
    handler: Callable[[dict[str, Any], Session], dict[str, Any]]


def _bounded_int(value: Any, *, field: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise ToolValidationError(f"{field} must be an integer from {minimum} to {maximum}")
    return value


def _query(value: Any) -> str:
    if not isinstance(value, str):
        raise ToolValidationError("query must be a string")
    query = re.sub(r"\\s+", " ", value).strip()
    if not 1 <= len(query) <= 1000:
        raise ToolValidationError("query must contain 1 to 1000 characters")
    return query


def _optional_date(value: Any, *, field: str) -> date | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ToolValidationError(f"{field} must be an ISO date")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ToolValidationError(f"{field} must be an ISO date") from exc


def _result_payload(result: "RetrievalResult") -> dict[str, Any]:
    return {
        "chunk_id": result.chunk_id,
        "document_id": result.document_id,
        "title": result.title,
        "content": result.content[:6000],
        "source_url": result.source_url,
        "published_at": result.published_at.isoformat() if result.published_at else None,
        "score": round(result.score, 4),
        "source": result.source_dict(),
    }


def search_campus_knowledge(arguments: dict[str, Any], _db: Session) -> dict[str, Any]:
    from app.rag.retrieval import retrieval_service

    query = _query(arguments.get("query"))
    top_k = _bounded_int(arguments.get("top_k", 5), field="top_k", minimum=1, maximum=5)
    category = arguments.get("category")
    if category is not None and (not isinstance(category, str) or len(category) > 100):
        raise ToolValidationError("category must be a string no longer than 100 characters")
    published_from = _optional_date(arguments.get("published_from"), field="published_from")
    published_to = _optional_date(arguments.get("published_to"), field="published_to")
    if published_from and published_to and published_from > published_to:
        raise ToolValidationError("published_from must not be later than published_to")
    results = retrieval_service.search(query)
    if category:
        # Category is metadata, not untrusted content.  The filter is deliberately
        # applied after retrieval until category-aware FAISS partitions are enabled.
        category_ids = set(
            _db.scalars(select(Document.id).where(Document.category == category)).all()
        )
        results = [item for item in results if item.document_id in category_ids]
    if published_from:
        results = [item for item in results if item.published_at and item.published_at >= published_from]
    if published_to:
        results = [item for item in results if item.published_at and item.published_at <= published_to]
    return {"query": query, "items": [_result_payload(item) for item in results[:top_k]]}


def get_document_metadata(arguments: dict[str, Any], db: Session) -> dict[str, Any]:
    document_id = _bounded_int(arguments.get("document_id"), field="document_id", minimum=1, maximum=2**31 - 1)
    document = db.get(Document, document_id)
    if document is None:
        return {"found": False, "document_id": document_id}
    return {
        "found": True,
        "document_id": document.id,
        "title": document.title,
        "category": document.category,
        "document_kind": document.document_kind.value,
        "source_url": document.source_url,
        "published_at": document.published_at.isoformat() if document.published_at else None,
        "status": document.status.value,
        "chunk_count": document.chunk_count,
    }


def retrieve_document_evidence(arguments: dict[str, Any], _db: Session) -> dict[str, Any]:
    from app.rag.retrieval import retrieval_service

    query = _query(arguments.get("query"))
    raw_ids = arguments.get("document_ids")
    if not isinstance(raw_ids, list) or not 1 <= len(raw_ids) <= 5:
        raise ToolValidationError("document_ids must contain 1 to 5 ids")
    document_ids = [_bounded_int(item, field="document_ids", minimum=1, maximum=2**31 - 1) for item in raw_ids]
    if len(set(document_ids)) != len(document_ids):
        raise ToolValidationError("document_ids must not contain duplicates")
    wanted = set(document_ids)
    results = [item for item in retrieval_service.search(query) if item.document_id in wanted]
    return {"query": query, "items": [_result_payload(item) for item in results[:5]]}


def get_current_date(arguments: dict[str, Any], _db: Session) -> dict[str, Any]:
    if arguments:
        raise ToolValidationError("get_current_date accepts no arguments")
    timezone = ZoneInfo("Asia/Shanghai")
    now = datetime.now(timezone)
    return {"date": now.date().isoformat(), "timezone": "Asia/Shanghai"}


class ToolRegistry:
    """Read-only tool registry.  Future write-capable tools need a separate policy gate."""

    def __init__(self) -> None:
        self._tools = {
            tool.name: tool
            for tool in (
                ToolDefinition("search_campus_knowledge", "Search the CampusQA knowledge index.", search_campus_knowledge),
                ToolDefinition("get_document_metadata", "Read public metadata for one knowledge document.", get_document_metadata),
                ToolDefinition("retrieve_document_evidence", "Retrieve evidence limited to selected documents.", retrieve_document_evidence),
                ToolDefinition("get_current_date", "Return the server current date.", get_current_date),
            )
        }

    def execute(self, name: str, arguments: dict[str, Any], db: Session) -> dict[str, Any]:
        tool = self._tools.get(name)
        if tool is None:
            raise ToolValidationError(f"tool is not allowlisted: {name}")
        if not isinstance(arguments, dict):
            raise ToolValidationError("tool arguments must be an object")
        return tool.handler(arguments, db)

    def names(self) -> tuple[str, ...]:
        return tuple(self._tools)


tool_registry = ToolRegistry()
