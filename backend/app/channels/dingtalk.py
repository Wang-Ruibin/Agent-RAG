from __future__ import annotations

import asyncio
import importlib
from datetime import UTC, datetime
from typing import Any

from app.channels.contracts import AdapterHealth, IncomingHandler, IncomingMessage, OutgoingMessage
from app.models.enums import BotPlatform


class DingTalkAdapter:
    """Official DingTalk Stream-mode adapter.

    The optional SDK owns its authenticated WebSocket connection.  We only
    translate its chatbot callbacks into the shared channel contract.
    """

    platform = BotPlatform.DINGTALK

    def __init__(self, *, bot_id: int, client_id: str, client_secret: str, on_message: IncomingHandler) -> None:
        self.bot_id = bot_id
        self.client_id = client_id
        self.client_secret = client_secret
        self.on_message = on_message
        self._task: asyncio.Task[None] | None = None
        self._client: Any = None
        self._last_error: str | None = None

    async def start(self) -> AdapterHealth:
        if not self.client_id or not self.client_secret:
            return AdapterHealth("ERROR", "client_id and client_secret are required", datetime.now(UTC))
        try:
            stream = importlib.import_module("dingtalk_stream")
        except ImportError:
            return AdapterHealth("ERROR", "install the dingtalk-stream package to enable DingTalk", datetime.now(UTC))
        if self._task is None or self._task.done():
            self._last_error = None
            self._client = self._build_client(stream)
            self._task = asyncio.create_task(asyncio.to_thread(self._run_client), name=f"dingtalk-{self.bot_id}")
        return AdapterHealth("RUNNING", self._last_error, datetime.now(UTC), ("text", "group", "private", "stream"))

    async def stop(self) -> AdapterHealth:
        client, self._client = self._client, None
        for method_name in ("stop", "disconnect", "close"):
            method = getattr(client, method_name, None)
            if callable(method):
                try:
                    result = method()
                    if hasattr(result, "__await__"):
                        await result
                except Exception as exc:  # SDKs do not expose a stable stop API across versions.
                    self._last_error = str(exc)[:500]
                break
        self._task = None
        return AdapterHealth("STOPPED", self._last_error, datetime.now(UTC))

    async def health(self) -> AdapterHealth:
        if self._task is None:
            return AdapterHealth("STOPPED", self._last_error, datetime.now(UTC))
        if self._task.done():
            return AdapterHealth("ERROR", self._last_error or "DingTalk Stream client stopped", datetime.now(UTC))
        return AdapterHealth("RUNNING", self._last_error, datetime.now(UTC), ("stream",))

    async def login_qr(self) -> dict[str, str]:
        return {
            "status": "developer_console_credentials_required",
            "note": "Create and authorize a DingTalk custom app in the DingTalk developer console, then save its client_id and client_secret.",
        }

    async def send(self, _message: OutgoingMessage) -> None:
        # Stream callbacks reply with the SDK's conversation token in _process.
        raise RuntimeError("DingTalk replies are only valid during an incoming Stream callback")

    def _build_client(self, stream: Any) -> Any:
        adapter = self

        class Handler(stream.ChatbotHandler):  # type: ignore[misc, valid-type]
            async def process(self, callback: Any) -> tuple[Any, str]:
                raw = callback.data if isinstance(callback.data, dict) else {}
                incoming = adapter._parse_payload(raw)
                if incoming is not None:
                    reply = await adapter.on_message(incoming)
                    if reply is not None:
                        message = stream.ChatbotMessage.from_dict(raw)
                        self.reply_text(reply.text, message)
                return stream.AckMessage.STATUS_OK, "OK"

        credential = stream.Credential(self.client_id, self.client_secret)
        client = stream.DingTalkStreamClient(credential)
        client.register_callback_handler(stream.chatbot.ChatbotMessage.TOPIC, Handler())
        return client

    def _run_client(self) -> None:
        try:
            self._client.start_forever()
        except Exception as exc:
            self._last_error = str(exc)[:500]

    def _parse_payload(self, payload: dict[str, Any]) -> IncomingMessage | None:
        sender_id = str(payload.get("senderId") or payload.get("senderStaffId") or "")
        message_id = str(payload.get("msgId") or "")
        conversation_id = str(payload.get("conversationId") or sender_id)
        if not sender_id or not message_id or not conversation_id:
            return None
        text = payload.get("text")
        content = str(text.get("content") or "") if isinstance(text, dict) else ""
        is_group = str(payload.get("conversationType") or "") == "2"
        at_users = payload.get("atUsers")
        mentioned = bool(at_users) if isinstance(at_users, list) else False
        return IncomingMessage(
            platform=self.platform,
            bot_id=self.bot_id,
            message_id=message_id,
            sender_id=sender_id,
            session_id=conversation_id,
            text=content.strip(),
            received_at=datetime.now(UTC),
            is_group=is_group,
            mentioned=mentioned,
        )
