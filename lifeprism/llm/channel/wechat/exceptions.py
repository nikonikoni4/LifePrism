"""微信 Channel 自定义异常模块"""


class WechatError(Exception):
    """微信 Channel 基础异常"""
    pass


class WechatAuthError(WechatError):
    """微信认证异常"""
    pass


class WechatAPIError(WechatError):
    """微信 API 调用异常"""
    pass


class WechatMessageError(WechatError):
    """微信消息处理异常"""
    pass


class WechatMediaError(WechatError):
    """微信媒体处理异常"""
    pass
