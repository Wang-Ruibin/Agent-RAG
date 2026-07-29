from __future__ import annotations

import asyncio

from app.channels.weixin_oc import WeixinOcAdapter


async def _ignore_message(_message):  # type: ignore[no-untyped-def]
    return None


def test_weixin_adapter_requires_official_login_configuration() -> None:
    adapter = WeixinOcAdapter(
        bot_id=1,
        api_base_url="",
        token="",
        wechat_uin="",
        account_id="",
        on_message=_ignore_message,
    )
    health = asyncio.run(adapter.start())
    assert health.status == "QR_REQUIRED"
    login = asyncio.run(adapter.login_qr())
    assert login["status"] == "terminal_login_required"


def test_weixin_adapter_parses_text_context_and_media_metadata() -> None:
    adapter = WeixinOcAdapter(
        bot_id=1,
        api_base_url="https://example.test",
        token="token",
        wechat_uin="uin",
        account_id="account",
        on_message=_ignore_message,
    )
    message = adapter._parse_message(  # noqa: SLF001 - protocol parser contract
        {
            "message_type": 1,
            "message_id": 99,
            "from_user_id": "user-1",
            "session_id": "session-1",
            "context_token": "context-token",
            "item_list": [
                {"type": 1, "text_item": {"text": "你好"}},
                {"type": 2, "image_item": {}},
                {"type": 5, "video_item": {}},
            ],
        }
    )
    assert message is not None
    assert message.text == "你好"
    assert [item["type"] for item in message.attachments] == ["image", "video"]
    assert adapter._context_tokens["session-1"] == "context-token"  # noqa: SLF001
    assert adapter._recipients["session-1"] == "user-1"  # noqa: SLF001
