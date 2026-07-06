# Channel 模块已重构，消息流转功能已迁移到 bus
# 未来用于外部通道接入（微信、QQ 等）
from lifeprism.llm.bus import bus
from lifeprism.llm.channel.wechat import WechatChannel, WechatConfig
from lifeprism.utils import LazySingleton

# 如果之后扩展了wechat channel，需要使用channel manager统一管理channel
wechat_channel: WechatChannel = LazySingleton(
    WechatChannel,
    WechatConfig(enabled=True, allow_from=["*"]),  # 允许所有用户
    bus,  # 注入消息总线
)

__all__ = ["wechat_channel"]
