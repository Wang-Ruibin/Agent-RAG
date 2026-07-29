from __future__ import annotations

import hmac
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request

from app.channels import channel_manager
from app.channels.qq_onebot import QQOneBotAdapter
from app.models.enums import BotPlatform, BotStatus
from app.models.orm import BotInstance
from app.services.bots import bot_service

from .dependencies import Database

router = APIRouter(prefix="/api/channels", tags=["channels"])


@router.post("/qq-onebot/{bot_id}/events")
async def qq_onebot_event(
    bot_id: int,
    request: Request,
    db: Database,
    x_onebot_token: str | None = Header(None),
) -> dict[str, object]:
    """Receive a OneBot v11 HTTP POST event after constant-time token verification."""
    bot = db.get(BotInstance, bot_id)
    if bot is None or bot.platform is not BotPlatform.QQ_ONEBOT:
        raise HTTPException(status_code=404, detail="QQ OneBot bot not found")
    credentials = bot_service.cipher.decrypt(bot.config_encrypted)
    expected = credentials.get("webhook_secret", "")
    if not expected or not x_onebot_token or not hmac.compare_digest(expected, x_onebot_token):
        raise HTTPException(status_code=401, detail="invalid OneBot event token")
    if bot.status is not BotStatus.RUNNING:
        raise HTTPException(status_code=409, detail="bot is not running")
    try:
        payload: Any = await request.json()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid JSON event") from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=422, detail="event must be an object")
    adapter = channel_manager.adapter_for(bot_id)
    if not isinstance(adapter, QQOneBotAdapter):
        raise HTTPException(status_code=409, detail="QQ OneBot adapter is not started")
    await adapter.handle_event(payload)
    return {"status": "ok", "retcode": 0}
