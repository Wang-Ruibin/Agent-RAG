from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from app.models.enums import BotPlatform


@dataclass(frozen=True, slots=True)
class IncomingMessage:
    platform: BotPlatform
    bot_id: int
    message_id: str
    sender_id: str
    session_id: str
    text: str
    received_at: datetime
    is_group: bool = False
    mentioned: bool = False
    attachments: tuple[dict[str, str], ...] = ()


@dataclass(frozen=True, slots=True)
class OutgoingMessage:
    session_id: str
    text: str
    reply_to_message_id: str | None = None


@dataclass(frozen=True, slots=True)
class AdapterHealth:
    status: str
    detail: str | None = None
    updated_at: datetime | None = None
    capabilities: tuple[str, ...] = field(default_factory=tuple)


class ChannelAdapter(Protocol):
    platform: BotPlatform

    async def start(self) -> AdapterHealth: ...

    async def stop(self) -> AdapterHealth: ...

    async def send(self, message: OutgoingMessage) -> None: ...

    async def health(self) -> AdapterHealth: ...

    async def login_qr(self) -> dict[str, str]: ...
