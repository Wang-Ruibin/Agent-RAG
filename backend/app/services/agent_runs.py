from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent.contracts import ToolEvent
from app.agent.router import ChatMode
from app.models.enums import AgentRunStatus
from app.models.orm import AgentRun, AgentStep, User, is_guest_user


def _now() -> datetime:
    return datetime.now(UTC)


class AgentRunService:
    def start(
        self,
        db: Session,
        user: User,
        *,
        conversation_id: int | None,
        requested_mode: str,
        selected_mode: ChatMode,
    ) -> AgentRun:
        run = AgentRun(
            public_id=str(uuid4()),
            user_id=None if is_guest_user(user) else user.id,
            conversation_id=conversation_id,
            requested_mode=requested_mode,
            selected_mode=selected_mode.value,
            status=AgentRunStatus.RUNNING,
        )
        db.add(run)
        db.commit()
        db.refresh(run)
        return run

    def finish(
        self,
        db: Session,
        run_id: int,
        events: list[ToolEvent],
        *,
        error: str | None = None,
    ) -> None:
        run = db.get(AgentRun, run_id)
        if run is None:
            return
        for event in events:
            db.add(
                AgentStep(
                    agent_run_id=run.id,
                    step_index=event.index,
                    tool_name=event.tool,
                    status=event.status,
                    summary=event.summary[:500],
                    duration_ms=event.duration_ms,
                )
            )
        run.status = AgentRunStatus.FAILED if error else AgentRunStatus.COMPLETE
        run.error = error[:500] if error else None
        run.finished_at = _now()
        db.commit()

    def get_for_owner(self, db: Session, user: User, public_id: str) -> AgentRun:
        if is_guest_user(user):
            raise LookupError("agent run not found")
        statement = select(AgentRun).where(AgentRun.public_id == public_id)
        if user.role.value != "ADMIN":
            statement = statement.where(AgentRun.user_id == user.id)
        run = db.scalar(statement)
        if run is None:
            raise LookupError("agent run not found")
        return run

    @staticmethod
    def serialize(db: Session, run: AgentRun) -> dict[str, object]:
        steps = db.scalars(
            select(AgentStep).where(AgentStep.agent_run_id == run.id).order_by(AgentStep.step_index)
        ).all()
        return {
            "id": run.public_id,
            "conversation_id": run.conversation_id,
            "requested_mode": run.requested_mode,
            "selected_mode": run.selected_mode,
            "status": run.status.value,
            "error": run.error,
            "created_at": run.created_at.isoformat(),
            "finished_at": run.finished_at.isoformat() if run.finished_at else None,
            "steps": [
                {
                    "index": step.step_index,
                    "tool": step.tool_name,
                    "status": step.status,
                    "summary": step.summary,
                    "duration_ms": step.duration_ms,
                }
                for step in steps
            ],
        }


agent_run_service = AgentRunService()
