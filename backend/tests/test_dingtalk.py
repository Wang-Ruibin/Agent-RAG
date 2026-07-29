from __future__ import annotations

import asyncio

from app.channels.dingtalk import DingTalkAdapter


async def _reply(_message):  # type: ignore[no-untyped-def]
    return None


def test_dingtalk_requires_custom_app_credentials() -> None:
    adapter = DingTalkAdapter(bot_id=1, client_id="", client_secret="", on_message=_reply)
    assert asyncio.run(adapter.start()).status == "ERROR"


def test_dingtalk_parses_private_and_group_payloads() -> None:
    adapter = DingTalkAdapter(bot_id=2, client_id="id", client_secret="secret", on_message=_reply)
    group = adapter._parse_payload(  # noqa: SLF001 - protocol parser contract
        {"senderId": "staff-1", "msgId": "m-1", "conversationId": "cid-1", "conversationType": "2", "text": {"content": " hello "}, "atUsers": [{"dingtalkId": "bot"}]}
    )
    private = adapter._parse_payload(  # noqa: SLF001
        {"senderId": "staff-2", "msgId": "m-2", "conversationId": "cid-2", "conversationType": "1", "text": {"content": "hi"}}
    )
    assert group is not None and group.is_group and group.mentioned and group.text == "hello"
    assert private is not None and not private.is_group and not private.mentioned
