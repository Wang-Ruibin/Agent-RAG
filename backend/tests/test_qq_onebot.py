from __future__ import annotations

import asyncio

from app.channels.contracts import OutgoingMessage
from app.channels.qq_onebot import QQOneBotAdapter


async def _reply(_message):  # type: ignore[no-untyped-def]
    return None


def test_qq_onebot_requires_protected_webhook_configuration() -> None:
    adapter = QQOneBotAdapter(
        bot_id=1,
        api_base_url="",
        access_token="",
        webhook_secret="",
        self_id="",
        on_message=_reply,
    )
    assert asyncio.run(adapter.start()).status == "ERROR"


def test_qq_onebot_parses_private_and_group_messages() -> None:
    adapter = QQOneBotAdapter(
        bot_id=1,
        api_base_url="https://onebot.example.test",
        access_token="",
        webhook_secret="event-secret",
        self_id="10001",
        on_message=_reply,
    )
    group = adapter._parse_event(  # noqa: SLF001 - parser is a protocol boundary
        {"post_type": "message", "message_type": "group", "message_id": 3, "user_id": 4, "group_id": 5, "raw_message": "[CQ:at,qq=10001] hello"}
    )
    private = adapter._parse_event(  # noqa: SLF001
        {"post_type": "message", "message_type": "private", "message_id": 6, "user_id": 7, "raw_message": "hello"}
    )
    assert group is not None and group.session_id == "group:5" and group.mentioned
    assert private is not None and private.session_id == "private:7" and not private.is_group


def test_qq_onebot_selects_send_endpoint(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    calls: list[tuple[str, dict[str, object]]] = []

    class Response:
        def raise_for_status(self) -> None: pass
        def json(self) -> dict[str, str]: return {"status": "ok"}

    class Client:
        async def __aenter__(self): return self
        async def __aexit__(self, *_args): return None
        async def post(self, url: str, **kwargs):
            calls.append((url, kwargs["json"]))
            return Response()

    monkeypatch.setattr("app.channels.qq_onebot.httpx.AsyncClient", lambda **_kwargs: Client())
    adapter = QQOneBotAdapter(bot_id=1, api_base_url="https://onebot.example.test", access_token="t", webhook_secret="s", self_id="", on_message=_reply)
    asyncio.run(adapter.send(OutgoingMessage(session_id="group:9", text="answer")))
    assert calls == [("https://onebot.example.test/send_group_msg", {"group_id": "9", "message": "answer"})]
