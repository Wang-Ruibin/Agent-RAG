from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

import httpx

from app.channels.contracts import AdapterHealth, IncomingMessage, OutgoingMessage
from app.models.enums import BotPlatform


IncomingHandler = Callable[[IncomingMessage], Awaitable[None]]


class WeixinOcAdapter:
    """Tencent OpenClaw WeChat HTTP protocol adapter.

    Login remains an operator action via Tencent's official OpenClaw plugin:
    ``openclaw channels login --channel openclaw-weixin``.  This class uses the
    documented post-login long-poll/send protocol and never implements or
    reverse engineers the QR-login flow itself.
    """

    platform = BotPlatform.WEIXIN_OC

    def __init__(
        self,
        *,
        bot_id: int,
        api_base_url: str,
        token: str,
        wechat_uin: str,
        account_id: str,
        on_message: IncomingHandler,
        request_timeout_seconds: float = 45.0,
    ) -> None:
        self.bot_id = bot_id
        self.api_base_url = api_base_url.rstrip("/")
        self.token = token
        self.wechat_uin = wechat_uin
        self.account_id = account_id
        self.on_message = on_message
        self.request_timeout_seconds = request_timeout_seconds
        self._cursor = ""
        self._context_tokens: dict[str, str] = {}
        self._poll_task: asyncio.Task[None] | None = None
        self._stopping = asyncio.Event()
        self._last_error: str | None = None

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "AuthorizationType": "ilink_bot_token",
            "Authorization": f"Bearer {self.token}",
            "X-WECHAT-UIN": self.wechat_uin,
        }

    async def start(self) -> AdapterHealth:
        if not all((self.api_base_url, self.token, self.wechat_uin, self.account_id)):
            return AdapterHealth("QR_REQUIRED", "run the official OpenClaw QR login first", datetime.now(UTC))
        if self._poll_task is None or self._poll_task.done():
            self._stopping.clear()
            self._poll_task = asyncio.create_task(self._poll_loop(), name=f"weixin-oc-{self.bot_id}")
        return AdapterHealth(
            "RUNNING",
            self._last_error,
            datetime.now(UTC),
            ("text", "image", "video", "file", "long_polling", "typing"),
        )

    async def stop(self) -> AdapterHealth:
        self._stopping.set()
        task = self._poll_task
        self._poll_task = None
        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        return AdapterHealth("STOPPED", None, datetime.now(UTC))

    async def health(self) -> AdapterHealth:
        if self._poll_task is None:
            return AdapterHealth("STOPPED", self._last_error, datetime.now(UTC))
        if self._poll_task.done():
            return AdapterHealth("ERROR", self._last_error or "long polling stopped", datetime.now(UTC))
        return AdapterHealth("RUNNING", self._last_error, datetime.now(UTC), ("long_polling",))

    async def login_qr(self) -> dict[str, str]:
        return {
            "status": "terminal_login_required",
            "command": "openclaw channels login --channel openclaw-weixin",
            "note": "Scan the QR code shown by the official Tencent OpenClaw plugin; this API never stores the QR credential.",
        }

    async def send(self, message: OutgoingMessage) -> None:
        context_token = self._context_tokens.get(message.session_id, "")
        payload = {
            "msg": {
                "to_user_id": message.session_id,
                "context_token": context_token,
                "item_list": [{"type": 1, "text_item": {"text": message.text}}],
            }
        }
        async with httpx.AsyncClient(timeout=self.request_timeout_seconds) as client:
            response = await client.post(
                f"{self.api_base_url}/sendmessage",
                headers=self._headers,
                json=payload,
            )
            response.raise_for_status()
            body = response.json()
            if body.get("ret", 0) != 0:
                raise RuntimeError(f"Weixin send failed: {body.get('errmsg', 'unknown error')}")

    async def _poll_loop(self) -> None:
        delay = 1.0
        while not self._stopping.is_set():
            try:
                async with httpx.AsyncClient(timeout=self.request_timeout_seconds) as client:
                    response = await client.post(
                        f"{self.api_base_url}/getupdates",
                        headers=self._headers,
                        json={"get_updates_buf": self._cursor},
                    )
                    response.raise_for_status()
                    payload = response.json()
                if payload.get("ret", 0) != 0:
                    raise RuntimeError(payload.get("errmsg") or f"ret={payload.get('ret')}")
                self._cursor = str(payload.get("get_updates_buf") or self._cursor)
                for raw in payload.get("msgs") or []:
                    incoming = self._parse_message(raw)
                    if incoming is not None:
                        await self.on_message(incoming)
                delay = 1.0
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self._last_error = str(exc)[:500]
                await asyncio.sleep(delay)
                delay = min(delay * 2, 30.0)

    def _parse_message(self, raw: Any) -> IncomingMessage | None:
        if not isinstance(raw, dict) or raw.get("message_type") != 1:
            return None
        sender_id = str(raw.get("from_user_id") or "")
        session_id = str(raw.get("session_id") or sender_id)
        message_id = str(raw.get("message_id") or "")
        if not sender_id or not session_id or not message_id:
            return None
        text_parts: list[str] = []
        attachments: list[dict[str, str]] = []
        for item in raw.get("item_list") or []:
            if not isinstance(item, dict):
                continue
            try:
                item_type = int(item.get("type") or 0)
            except (TypeError, ValueError):
                continue
            if item_type == 1 and isinstance(item.get("text_item"), dict):
                text_parts.append(str(item["text_item"].get("text") or ""))
            elif item_type in {2, 4, 5}:
                attachments.append({"type": {2: "image", 4: "file", 5: "video"}[item_type]})
        context_token = raw.get("context_token")
        if isinstance(context_token, str) and context_token:
            self._context_tokens[session_id] = context_token
        return IncomingMessage(
            platform=self.platform,
            bot_id=self.bot_id,
            message_id=message_id,
            sender_id=sender_id,
            session_id=session_id,
            text="\n".join(part for part in text_parts if part).strip(),
            received_at=datetime.fromtimestamp(float(raw.get("create_time_ms") or 0) / 1000, tz=UTC)
            if raw.get("create_time_ms")
            else datetime.now(UTC),
            attachments=tuple(attachments),
        )
