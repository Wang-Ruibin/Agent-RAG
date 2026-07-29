from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx

from app.channels.contracts import AdapterHealth, IncomingHandler, IncomingMessage, OutgoingMessage
from app.models.enums import BotPlatform


class QQOneBotAdapter:
    """OneBot v11 HTTP adapter.

    A compatible QQ gateway posts message events to our authenticated webhook;
    replies are sent through the gateway's documented v11 HTTP API.  This keeps
    the application independent of any unofficial QQ client implementation.
    """

    platform = BotPlatform.QQ_ONEBOT

    def __init__(
        self,
        *,
        bot_id: int,
        api_base_url: str,
        access_token: str,
        webhook_secret: str,
        self_id: str,
        on_message: IncomingHandler,
    ) -> None:
        self.bot_id = bot_id
        self.api_base_url = api_base_url.rstrip("/")
        self.access_token = access_token
        self.webhook_secret = webhook_secret
        self.self_id = self_id
        self.on_message = on_message
        self._running = False
        self._last_error: str | None = None

    async def start(self) -> AdapterHealth:
        if not self.api_base_url or not self.webhook_secret:
            return AdapterHealth("ERROR", "api_base_url and webhook_secret are required", datetime.now(UTC))
        self._running = True
        return AdapterHealth("RUNNING", None, datetime.now(UTC), ("text", "group", "private", "onebot_v11_http"))

    async def stop(self) -> AdapterHealth:
        self._running = False
        return AdapterHealth("STOPPED", None, datetime.now(UTC))

    async def health(self) -> AdapterHealth:
        return AdapterHealth("RUNNING" if self._running else "STOPPED", self._last_error, datetime.now(UTC), ("onebot_v11_http",))

    async def login_qr(self) -> dict[str, str]:
        return {
            "status": "gateway_configuration_required",
            "note": "Log in to QQ in your compliant OneBot v11 gateway, then configure its HTTP event callback with this bot's protected endpoint.",
        }

    async def send(self, message: OutgoingMessage) -> None:
        if message.session_id.startswith("group:"):
            endpoint, payload = "/send_group_msg", {"group_id": message.session_id.removeprefix("group:"), "message": message.text}
        elif message.session_id.startswith("private:"):
            endpoint, payload = "/send_private_msg", {"user_id": message.session_id.removeprefix("private:"), "message": message.text}
        else:
            raise ValueError("invalid OneBot session id")
        headers = {"Authorization": f"Bearer {self.access_token}"} if self.access_token else {}
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(f"{self.api_base_url}{endpoint}", headers=headers, json=payload)
            response.raise_for_status()
            body = response.json()
        if isinstance(body, dict) and body.get("status") not in (None, "ok"):
            raise RuntimeError(f"OneBot send failed: {body.get('wording') or body.get('msg') or 'unknown error'}")

    async def handle_event(self, event: dict[str, Any]) -> None:
        if not self._running or event.get("post_type") != "message":
            return
        incoming = self._parse_event(event)
        if incoming is None:
            return
        try:
            reply = await self.on_message(incoming)
            if reply is not None:
                await self.send(reply)
        except Exception as exc:
            self._last_error = str(exc)[:500]
            raise

    def _parse_event(self, event: dict[str, Any]) -> IncomingMessage | None:
        message_type = event.get("message_type")
        sender_id = str(event.get("user_id") or "")
        message_id = str(event.get("message_id") or "")
        if message_type not in {"group", "private"} or not sender_id or not message_id:
            return None
        is_group = message_type == "group"
        group_id = str(event.get("group_id") or "")
        if is_group and not group_id:
            return None
        session_id = f"group:{group_id}" if is_group else f"private:{sender_id}"
        raw_text = str(event.get("raw_message") or event.get("message") or "").strip()
        current_self_id = self.self_id or str(event.get("self_id") or "")
        mentioned = bool(current_self_id and (f"[CQ:at,qq={current_self_id}]" in raw_text or f"@{current_self_id}" in raw_text))
        return IncomingMessage(
            platform=self.platform,
            bot_id=self.bot_id,
            message_id=message_id,
            sender_id=sender_id,
            session_id=session_id,
            text=raw_text,
            received_at=datetime.now(UTC),
            is_group=is_group,
            mentioned=mentioned,
        )
