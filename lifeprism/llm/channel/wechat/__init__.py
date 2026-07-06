"""微信 Channel 入口模块
本模块提供微信平台的 Channel 接入能力，包含认证、配置等核心组件的导出。
"""

from lifeprism.llm.channel.wechat.channel import WechatChannel
from lifeprism.llm.channel.wechat.config import WechatConfig

__all__ = ["WechatChannel", "WechatConfig"]
