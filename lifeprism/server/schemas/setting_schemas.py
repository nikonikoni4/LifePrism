"""
Setting 界面的 schemas

提供配置管理相关的请求/响应模型
"""

from pydantic import BaseModel, Field
from typing import Dict, List, Optional


class ProviderModelHistory(BaseModel):
    """单个服务商的模型历史快照"""
    api_base: str = Field(default="", description="该服务商最近保存的 API Base")
    models: List[str] = Field(default_factory=list, description="该服务商的模型历史列表")


class SettingItems(BaseModel):
    """配置项完整模型"""
    # 用户配置
    user_name: str = Field(description="用户名称")
    # API 配置
    api_key: Optional[str] = Field(default=None, description="API Key (显示时脱敏)")
    provider: str = Field(description="LLM Provider")
    provider_list: List[str] = Field(description="支持的模型服务商列表")
    provider_id_map: Dict[str, str] = Field(default={}, description="服务商显示名称到 ID 的映射")
    model: str = Field(description="模型选择")
    api_base: str = Field(default="", description="当前 API Base")
    model_history: Dict[str, ProviderModelHistory] = Field(default={}, description="按服务商存储的模型历史")
    input_tokens_cost: float = Field(description="输入token单价 /1k")
    output_tokens_cost: float = Field(description="输出token单价 /1k")
    # 分类配置
    classification_mode: str = Field(description="分类模式")
    long_log_threshold: int = Field(description="长时长阈值 (秒)")
    # 多用途应用配置
    multi_purpose_app_names: List[str] = Field(description="多用途/浏览器应用名称列表")
    # 路径配置
    aw_db_path: str = Field(description="Activity Watch DB 来源路径")
    lifeprism_data_path: str = Field(description="LifePrism 数据目录路径")
    config_base_path: str = Field(description="配置文件所在目录路径")
    # 数据清洗配置
    data_cleaning_threshold: int = Field(description="数据清洗时长阈值 (秒)")
    # 截图配置
    scheduled_screenshot_interval_seconds: int = Field(description="固定截图周期 (秒)")
    active_screenshot_frequency_level: int = Field(description="主动截图频率等级")
    keyboard_keepalive_seconds: int = Field(description="键盘 keepalive 时长 (秒)")
    mouse_keepalive_seconds: int = Field(description="鼠标 keepalive 时长 (秒)")
    enter_screenshot_delay_ms: int = Field(description="Enter 截图延迟 (毫秒)")
    screenshot_retention_days: int = Field(description="截图保留天数")
    cleanup_check_interval_seconds: int = Field(description="截图清理扫描周期 (秒)")


class SettingsResponse(BaseModel):
    """获取配置响应"""
    settings: SettingItems
    message: str = "success"


class UpdateSettingsRequest(BaseModel):
    """更新配置请求 (部分更新)"""
    user_name: Optional[str] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    api_base: Optional[str] = None
    input_tokens_cost: Optional[float] = None
    output_tokens_cost: Optional[float] = None
    classification_mode: Optional[str] = None
    long_log_threshold: Optional[int] = None
    multi_purpose_app_names: Optional[List[str]] = None
    aw_db_path: Optional[str] = None
    lifeprism_data_path: Optional[str] = None
    data_cleaning_threshold: Optional[int] = None
    scheduled_screenshot_interval_seconds: Optional[int] = None
    active_screenshot_frequency_level: Optional[int] = None
    keyboard_keepalive_seconds: Optional[int] = None
    mouse_keepalive_seconds: Optional[int] = None
    enter_screenshot_delay_ms: Optional[int] = None
    screenshot_retention_days: Optional[int] = None
    cleanup_check_interval_seconds: Optional[int] = None
    screenshot_monitor: Optional[bool] = None


class UpdateApiKeyRequest(BaseModel):
    """更新 API Key 请求"""
    api_key: str = Field(description="新的 API Key")
    provider_id: Optional[str] = Field(default=None, description="服务商 ID，如 aliyun, openai 等")


class UpdateApiKeyResponse(BaseModel):
    """更新 API Key 响应"""
    success: bool
    message: str


class ProviderInfo(BaseModel):
    """服务商信息"""
    name: str = Field(description="服务商 ID")
    display_name: str = Field(description="服务商显示名称")
    default_model: str = Field(description="默认模型")
    default_api_base: str = Field(default="", description="默认 API Base URL")
    has_api_key: bool = Field(description="是否需要 API Key")


class ProviderListResponse(BaseModel):
    """获取服务商列表响应"""
    providers: List[ProviderInfo]


class ValidatePathRequest(BaseModel):
    """路径验证请求"""
    path: str = Field(..., description="要验证的路径")
    path_type: str = Field(..., description="路径类型: lifeprism_data | aw_db")


class ValidatePathResponse(BaseModel):
    """路径验证响应"""
    valid: bool = Field(description="路径是否有效")
    message: str = Field(description="验证结果消息")


class MigrateDataPathRequest(BaseModel):
    """数据路径迁移请求"""
    target_base_path: str = Field(..., description="目标基础路径（不含 lifeprismData）")
    migrate_data: bool = Field(default=True, description="是否迁移数据，False 则仅切换路径")


class MigrateDataPathResponse(BaseModel):
    """数据路径迁移响应"""
    success: bool = Field(description="是否迁移成功")
    message: str = Field(description="结果消息")
    new_path: Optional[str] = Field(default=None, description="迁移后的完整数据路径")


class TestVlmResponse(BaseModel):
    """测试 VLM 能力响应"""
    success: bool = Field(description="测试是否成功")
    message: str = Field(description="结果消息")
    is_vlm: bool = Field(description="测试结果，该模型是否具备 VLM 能力")
    model_response: Optional[str] = Field(default=None, description="模型回复内容")
    cache_updated: bool = Field(default=False, description="缓存是否已更新")
