from dataclasses import dataclass, field


@dataclass
class WechatConfig:
    """
    微信 channel 配置

    Attributes:
        enabled: 是否启用微信 channel
        base_url: 微信 API 基础 URL
        cdn_base_url: 微信 CDN 基础 URL，用于媒体文件访问
        poll_timeout: 长轮询超时时间（秒）
        allow_from: 允许接收消息的用户列表（微信 ID）
    """
    enabled: bool = False
    base_url: str = "https://ilinkai.weixin.qq.com"
    cdn_base_url: str = "https://novac2c.cdn.weixin.qq.com/c2c"
    poll_timeout: int = 35
    allow_from: list[str] = field(default_factory=list)
