from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from app.channels.contracts import AdapterHealth, ChannelAdapter
from app.models.enums import BotPlatform


class ChannelManager:
    """Owns adapter lifecycle; adapters are registered by bot id, never by secrets."""

    def __init__(self) -> None:
        self._adapters: dict[int, ChannelAdapter] = {}
        self._lock = asyncio.Lock()

    async def register(self, bot_id: int, adapter: ChannelAdapter) -> None:
        async with self._lock:
            previous = self._adapters.pop(bot_id, None)
        if previous is not None:
            await previous.stop()
        async with self._lock:
            self._adapters[bot_id] = adapter

    async def start(self, bot_id: int) -> AdapterHealth:
        adapter = self._adapters.get(bot_id)
        if adapter is None:
            return AdapterHealth("STOPPED", "adapter is not configured", datetime.now(UTC))
        return await adapter.start()

    async def stop(self, bot_id: int) -> AdapterHealth:
        adapter = self._adapters.get(bot_id)
        if adapter is None:
            return AdapterHealth("STOPPED", None, datetime.now(UTC))
        return await adapter.stop()

    async def health(self, bot_id: int) -> AdapterHealth:
        adapter = self._adapters.get(bot_id)
        if adapter is None:
            return AdapterHealth("STOPPED", "adapter is not configured", datetime.now(UTC))
        return await adapter.health()

    async def login_qr(self, bot_id: int) -> dict[str, str]:
        adapter = self._adapters.get(bot_id)
        if adapter is None:
            return {"status": "not_configured"}
        return await adapter.login_qr()

    async def shutdown(self) -> None:
        async with self._lock:
            adapters = list(self._adapters.values())
            self._adapters.clear()
        await asyncio.gather(*(adapter.stop() for adapter in adapters), return_exceptions=True)

    def platform_for(self, bot_id: int) -> BotPlatform | None:
        adapter = self._adapters.get(bot_id)
        return adapter.platform if adapter else None

    def adapter_for(self, bot_id: int) -> ChannelAdapter | None:
        return self._adapters.get(bot_id)


channel_manager = ChannelManager()
