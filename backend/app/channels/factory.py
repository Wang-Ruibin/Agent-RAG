from __future__ import annotations

from app.channels.contracts import ChannelAdapter
from app.channels.dispatcher import channel_dispatcher
from app.channels.dingtalk import DingTalkAdapter
from app.channels.qq_onebot import QQOneBotAdapter
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
    if bot.platform is BotPlatform.QQ_ONEBOT:
        return QQOneBotAdapter(
            bot_id=bot.id,
            api_base_url=credentials.get("api_base_url", ""),
            access_token=credentials.get("access_token", ""),
            webhook_secret=credentials.get("webhook_secret", ""),
            self_id=credentials.get("self_id", ""),
            on_message=channel_dispatcher.handle,
        )
    if bot.platform is BotPlatform.DINGTALK:
        return DingTalkAdapter(
            bot_id=bot.id,
            client_id=credentials.get("client_id", ""),
            client_secret=credentials.get("client_secret", ""),
            on_message=channel_dispatcher.handle,
        )
    raise AdapterUnavailableError(f"{bot.platform.value} adapter is not enabled in this build")
