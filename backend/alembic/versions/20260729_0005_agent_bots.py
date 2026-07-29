"""Add persistent, secret-safe agent traces and external bot mappings."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260729_0005"
down_revision = "20260717_0004"
branch_labels = None
depends_on = None


bot_platform = sa.Enum("WEIXIN_OC", "DINGTALK", "QQ_ONEBOT", name="botplatform")
bot_status = sa.Enum(
    "STOPPED", "STARTING", "RUNNING", "QR_REQUIRED", "ERROR", name="botstatus"
)
message_direction = sa.Enum("INBOUND", "OUTBOUND", name="platformmessagedirection")
agent_run_status = sa.Enum("RUNNING", "COMPLETE", "FAILED", "CANCELLED", name="agentrunstatus")


def upgrade() -> None:
    op.create_table(
        "bot_instances",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("platform", bot_platform, nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("config_encrypted", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", bot_status, nullable=False, server_default="STOPPED"),
        sa.Column("status_detail", sa.String(length=500), nullable=True),
        sa.Column("mention_required", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("command_prefix", sa.String(length=32), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index("ix_bot_instances_platform", "bot_instances", ["platform"])
    op.create_index("ix_bot_instances_status", "bot_instances", ["status"])

    op.create_table(
        "platform_identities",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("bot_instance_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("external_user_id", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["bot_instance_id"], ["bot_instances.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("bot_instance_id", "external_user_id"),
    )
    op.create_index("ix_platform_identities_bot_instance_id", "platform_identities", ["bot_instance_id"])
    op.create_index("ix_platform_identities_user_id", "platform_identities", ["user_id"])

    op.create_table(
        "platform_sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("bot_instance_id", sa.Integer(), nullable=False),
        sa.Column("owner_identity_id", sa.Integer(), nullable=True),
        sa.Column("conversation_id", sa.Integer(), nullable=False),
        sa.Column("external_session_id", sa.String(length=255), nullable=False),
        sa.Column("is_group", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["bot_instance_id"], ["bot_instances.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["owner_identity_id"], ["platform_identities.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("bot_instance_id", "external_session_id"),
    )
    op.create_index("ix_platform_sessions_bot_instance_id", "platform_sessions", ["bot_instance_id"])
    op.create_index("ix_platform_sessions_owner_identity_id", "platform_sessions", ["owner_identity_id"])
    op.create_index("ix_platform_sessions_conversation_id", "platform_sessions", ["conversation_id"])

    op.create_table(
        "platform_messages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("bot_instance_id", sa.Integer(), nullable=False),
        sa.Column("platform_session_id", sa.Integer(), nullable=True),
        sa.Column("platform_identity_id", sa.Integer(), nullable=True),
        sa.Column("external_message_id", sa.String(length=255), nullable=False),
        sa.Column("direction", message_direction, nullable=False),
        sa.Column("content_preview", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("attachments_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["bot_instance_id"], ["bot_instances.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["platform_identity_id"], ["platform_identities.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["platform_session_id"], ["platform_sessions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("bot_instance_id", "external_message_id"),
    )
    for column in ("bot_instance_id", "platform_session_id", "platform_identity_id"):
        op.create_index(f"ix_platform_messages_{column}", "platform_messages", [column])

    op.create_table(
        "agent_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("public_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("conversation_id", sa.Integer(), nullable=True),
        sa.Column("requested_mode", sa.String(length=16), nullable=False, server_default="auto"),
        sa.Column("selected_mode", sa.String(length=16), nullable=False, server_default="rag"),
        sa.Column("status", agent_run_status, nullable=False, server_default="RUNNING"),
        sa.Column("error", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("public_id"),
    )
    for column in ("public_id", "user_id", "conversation_id"):
        op.create_index(f"ix_agent_runs_{column}", "agent_runs", [column], unique=column == "public_id")

    op.create_table(
        "agent_steps",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("agent_run_id", sa.Integer(), nullable=False),
        sa.Column("step_index", sa.Integer(), nullable=False),
        sa.Column("tool_name", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("summary", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("duration_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["agent_run_id"], ["agent_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("agent_run_id", "step_index"),
    )
    op.create_index("ix_agent_steps_agent_run_id", "agent_steps", ["agent_run_id"])


def downgrade() -> None:
    op.drop_table("agent_steps")
    op.drop_table("agent_runs")
    op.drop_table("platform_messages")
    op.drop_table("platform_sessions")
    op.drop_table("platform_identities")
    op.drop_table("bot_instances")
