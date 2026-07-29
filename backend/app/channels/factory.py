from __future__ import annotations

from app.channels.contracts import ChannelAdapter
from app.channels.dispatcher import channel_dispatcher
from app.channels.weixin_oc import WeixinOcAdapter
from app.models.enums import BotPlatform
from app.models.orm import BotInstance
from app.services.bots import bot_service


class AdapterUnavailableError(ValueError):
    pass


def build_adapter(bot: BotInstance) -> ChannelAdapter:
    credentials = bot_service.cipher.decrypt(bot.config_encrypted)
    if bot.platform is BotPlatform.WEIXIN_OC:
        return WeixinOcAdapter(
            bot_id=bot.id,
            api_base_url=credentials.get("api_base_url", ""),
            token=credentials.get("token", ""),
            wechat_uin=credentials.get("wechat_uin", ""),
            account_id=credentials.get("account_id", ""),
            on_message=channel_dispatcher.handle,
        )
    raise AdapterUnavailableError(f"{bot.platform.value} adapter is not enabled in this build")
