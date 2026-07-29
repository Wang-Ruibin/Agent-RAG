from __future__ import annotations

import json
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.enums import BotPlatform, BotStatus
from app.models.orm import BotInstance, User


class BotConfigurationError(ValueError):
    pass


class CredentialCipher:
    """Encrypt bot credentials at rest; callers never receive decrypted values."""

    @staticmethod
    def _fernet() -> Fernet:
        key = settings.bot_credentials_encryption_key.get_secret_value().strip()
        if not key:
            raise BotConfigurationError("BOT_CREDENTIALS_ENCRYPTION_KEY is not configured")
        try:
            return Fernet(key.encode("ascii"))
        except (ValueError, UnicodeEncodeError) as exc:
            raise BotConfigurationError("BOT_CREDENTIALS_ENCRYPTION_KEY is invalid") from exc

    def encrypt(self, value: dict[str, str]) -> str:
        return self._fernet().encrypt(json.dumps(value, ensure_ascii=False).encode("utf-8")).decode("ascii")

    def decrypt(self, value: str) -> dict[str, str]:
        if not value:
            return {}
        try:
            payload = self._fernet().decrypt(value.encode("ascii"))
            decoded = json.loads(payload.decode("utf-8"))
        except (InvalidToken, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise BotConfigurationError("saved bot credentials cannot be decrypted") from exc
        if not isinstance(decoded, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in decoded.items()):
            raise BotConfigurationError("saved bot credentials are malformed")
        return decoded


def _credentials(value: dict[str, Any]) -> dict[str, str]:
    if len(value) > 32:
        raise BotConfigurationError("at most 32 credential fields are allowed")
    result: dict[str, str] = {}
    for key, item in value.items():
        if not isinstance(key, str) or not key or len(key) > 120 or not isinstance(item, str) or len(item) > 8000:
            raise BotConfigurationError("credentials must be short string key/value pairs")
        result[key] = item
    return result


class BotService:
    cipher = CredentialCipher()

    @staticmethod
    def serialize(bot: BotInstance) -> dict[str, object]:
        return {
            "id": bot.id,
            "platform": bot.platform.value,
            "name": bot.name,
            "status": bot.status.value,
            "status_detail": bot.status_detail,
            "mention_required": bot.mention_required,
            "command_prefix": bot.command_prefix,
            "created_at": bot.created_at.isoformat(),
            "updated_at": bot.updated_at.isoformat(),
        }

    def list(self, db: Session) -> list[BotInstance]:
        return db.scalars(select(BotInstance).order_by(BotInstance.id.desc())).all()

    def create(
        self,
        db: Session,
        user: User,
        *,
        platform: BotPlatform,
        name: str,
        credentials: dict[str, Any],
        mention_required: bool,
        command_prefix: str | None,
    ) -> BotInstance:
        normalized_name = name.strip()
        if not 2 <= len(normalized_name) <= 120:
            raise BotConfigurationError("bot name must contain 2 to 120 characters")
        if db.scalar(select(BotInstance.id).where(BotInstance.name == normalized_name)) is not None:
            raise BotConfigurationError("bot name already exists")
        bot = BotInstance(
            platform=platform,
            name=normalized_name,
            config_encrypted=self.cipher.encrypt(_credentials(credentials)),
            mention_required=mention_required,
            command_prefix=(command_prefix or "").strip() or None,
            created_by=user.id,
        )
        db.add(bot)
        db.commit()
        db.refresh(bot)
        return bot

    def update(self, db: Session, bot_id: int, **changes: Any) -> BotInstance:
        bot = db.get(BotInstance, bot_id)
        if bot is None:
            raise LookupError("bot not found")
        if "name" in changes and changes["name"] is not None:
            name = changes["name"].strip()
            if not 2 <= len(name) <= 120:
                raise BotConfigurationError("bot name must contain 2 to 120 characters")
            bot.name = name
        if "credentials" in changes and changes["credentials"] is not None:
            bot.config_encrypted = self.cipher.encrypt(_credentials(changes["credentials"]))
        if "mention_required" in changes and changes["mention_required"] is not None:
            bot.mention_required = bool(changes["mention_required"])
        if "command_prefix" in changes and changes["command_prefix"] is not None:
            bot.command_prefix = str(changes["command_prefix"]).strip() or None
        db.commit()
        db.refresh(bot)
        return bot

    def set_status(self, db: Session, bot_id: int, status: BotStatus, detail: str | None = None) -> BotInstance:
        bot = db.get(BotInstance, bot_id)
        if bot is None:
            raise LookupError("bot not found")
        bot.status = status
        bot.status_detail = detail[:500] if detail else None
        db.commit()
        db.refresh(bot)
        return bot

    def delete(self, db: Session, bot_id: int) -> None:
        bot = db.get(BotInstance, bot_id)
        if bot is None:
            raise LookupError("bot not found")
        db.delete(bot)
        db.commit()


bot_service = BotService()
