from __future__ import annotations

import hashlib
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.enums import PlatformMessageDirection, Role
from app.models.orm import BotInstance, Conversation, PlatformIdentity, PlatformMessage, PlatformSession, User


@dataclass(frozen=True, slots=True)
class BoundPlatformUser:
    user: User
    identity: PlatformIdentity


class PlatformIdentityService:
    """Binds external senders to normal STUDENT accounts without exposing login credentials."""

    @staticmethod
    def _synthetic_email(bot_id: int, external_user_id: str) -> str:
        digest = hashlib.sha256(external_user_id.encode("utf-8")).hexdigest()[:32]
        return f"bot-{bot_id}-{digest}@platform.campusqa.internal"

    def bind_sender(
        self,
        db: Session,
        bot: BotInstance,
        *,
        external_user_id: str,
        display_name: str | None,
    ) -> BoundPlatformUser:
        external_user_id = external_user_id.strip()
        if not external_user_id or len(external_user_id) > 255:
            raise ValueError("external sender id is invalid")
        identity = db.scalar(
            select(PlatformIdentity).where(
                PlatformIdentity.bot_instance_id == bot.id,
                PlatformIdentity.external_user_id == external_user_id,
            )
        )
        if identity is not None:
            user = db.get(User, identity.user_id)
            if user is None:
                raise LookupError("bound platform user not found")
            if display_name and identity.display_name != display_name[:255]:
                identity.display_name = display_name[:255]
                db.commit()
            return BoundPlatformUser(user, identity)

        safe_name = (display_name or f"{bot.platform.value} user")[:80]
        user = User(
            name=f"platform-{bot.id}-{hashlib.sha256(external_user_id.encode()).hexdigest()[:12]}",
            email=self._synthetic_email(bot.id, external_user_id),
            password_hash=hash_password(hashlib.sha256(external_user_id.encode()).hexdigest()),
            role=Role.STUDENT,
            is_active=True,
        )
        db.add(user)
        db.flush()
        identity = PlatformIdentity(
            bot_instance_id=bot.id,
            user_id=user.id,
            external_user_id=external_user_id,
            display_name=safe_name,
        )
        db.add(identity)
        try:
            db.commit()
        except IntegrityError:
            # Concurrent delivery of a first message is safe: resolve the
            # unique identity created by the other worker instead of duplicating.
            db.rollback()
            identity = db.scalar(
                select(PlatformIdentity).where(
                    PlatformIdentity.bot_instance_id == bot.id,
                    PlatformIdentity.external_user_id == external_user_id,
                )
            )
            if identity is None:
                raise
            user = db.get(User, identity.user_id)
            if user is None:
                raise LookupError("bound platform user not found")
        else:
            db.refresh(user)
            db.refresh(identity)
        return BoundPlatformUser(user, identity)

    def get_or_create_session(
        self,
        db: Session,
        bot: BotInstance,
        identity: PlatformIdentity,
        *,
        external_session_id: str,
        is_group: bool,
    ) -> PlatformSession:
        session = db.scalar(
            select(PlatformSession).where(
                PlatformSession.bot_instance_id == bot.id,
                PlatformSession.external_session_id == external_session_id,
            )
        )
        if session is not None:
            return session
        conversation = Conversation(user_id=identity.user_id, title=f"{bot.name}: {external_session_id[:80]}")
        db.add(conversation)
        db.flush()
        session = PlatformSession(
            bot_instance_id=bot.id,
            owner_identity_id=identity.id,
            conversation_id=conversation.id,
            external_session_id=external_session_id[:255],
            is_group=is_group,
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        return session

    def record_inbound(
        self,
        db: Session,
        *,
        bot_id: int,
        session_id: int,
        identity_id: int,
        external_message_id: str,
        content_preview: str,
        attachments: list[dict[str, str]] | None = None,
    ) -> bool:
        """Return False for an already-seen platform message (idempotent delivery)."""
        existing = db.scalar(
            select(PlatformMessage.id).where(
                PlatformMessage.bot_instance_id == bot_id,
                PlatformMessage.external_message_id == external_message_id,
            )
        )
        if existing is not None:
            return False
        db.add(
            PlatformMessage(
                bot_instance_id=bot_id,
                platform_session_id=session_id,
                platform_identity_id=identity_id,
                external_message_id=external_message_id[:255],
                direction=PlatformMessageDirection.INBOUND,
                content_preview=content_preview[:500],
                attachments_json=(attachments or [])[:10],
            )
        )
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            return False
        return True


platform_identity_service = PlatformIdentityService()
