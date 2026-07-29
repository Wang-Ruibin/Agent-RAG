from __future__ import annotations

import asyncio
from uuid import uuid4

from app.channels.contracts import IncomingMessage, OutgoingMessage
from app.core.database import SessionLocal
from app.models.enums import PlatformMessageDirection
from app.models.orm import BotInstance, PlatformMessage
from app.services.chat import chat_service
from app.services.platform_identities import platform_identity_service


class ChannelDispatcher:
    """Turns normalized platform messages into regular, attributable CampusQA chats."""

    async def handle(self, message: IncomingMessage) -> OutgoingMessage | None:
        return await asyncio.to_thread(self._handle_sync, message)

    @staticmethod
    def _handle_sync(message: IncomingMessage) -> OutgoingMessage | None:
        with SessionLocal() as db:
            bot = db.get(BotInstance, message.bot_id)
            if bot is None or bot.status.value not in {"RUNNING", "QR_REQUIRED"}:
                return None
            question = message.text.strip()
            if message.is_group:
                prefix = bot.command_prefix or ""
                prefix_match = bool(prefix and question.startswith(prefix))
                if bot.mention_required and not message.mentioned and not prefix_match:
                    return None
                if prefix_match:
                    question = question[len(prefix) :].strip()
            if not question:
                return None

            bound = platform_identity_service.bind_sender(
                db,
                bot,
                external_user_id=message.sender_id,
                display_name=None,
            )
            session = platform_identity_service.get_or_create_session(
                db,
                bot,
                bound.identity,
                external_session_id=message.session_id,
                is_group=message.is_group,
            )
            if not platform_identity_service.record_inbound(
                db,
                bot_id=bot.id,
                session_id=session.id,
                identity_id=bound.identity.id,
                external_message_id=message.message_id,
                content_preview=question,
                attachments=list(message.attachments),
            ):
                return None
            result = chat_service.complete(
                db,
                bound.user,
                question,
                session.conversation_id,
            )
            db.add(
                PlatformMessage(
                    bot_instance_id=bot.id,
                    platform_session_id=session.id,
                    platform_identity_id=bound.identity.id,
                    external_message_id=f"out:{uuid4()}",
                    direction=PlatformMessageDirection.OUTBOUND,
                    content_preview=str(result["answer"])[:500],
                    attachments_json=[],
                )
            )
            db.commit()
            return OutgoingMessage(
                session_id=message.session_id,
                text=str(result["answer"]),
                reply_to_message_id=message.message_id,
            )


channel_dispatcher = ChannelDispatcher()
