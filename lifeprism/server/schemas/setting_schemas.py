"""
Setting 界面的 schemas

提供配置管理相关的请求/响应模型
"""

from pydantic import BaseModel, Field
from typing import List, Optional


class SettingItems(BaseModel):
    """配置项完整模型"""
    # 用户配置
    user_name: str = Field(description="用户名称")
    # API 配置
    api_key: Optional[str] = Field(default=None, description="API Key (显示时脱敏)")
    provider: str = Field(description="LLM Provider")
    provider_list: List[str] = Field(description="支持的模型服务商列表")
    model: str = Field(description="模型选择")
    input_tokens_cost: float = Field(description="输入token单价 /1k")
    output_tokens_cost: float = Field(description="输出token单价 /1k")
    # 分类配置
    classification_mode: str = Field(description="分类模式")
    long_log_threshold: int = Field(description="长时长阈值 (秒)")
    # 多用途应用配置
    multi_purpose_app_names: List[str] = Field(description="多用途/浏览器应用名称列表")
    # 数据库路径配置
    aw_db_path: str = Field(description="Activity Watch DB 来源路径")
    lw_db_path: str = Field(description="Life Watch DB 保存路径")
    chat_db_path: str = Field(description="Chat DB 保存路径")
    # 数据清洗配置
    data_cleaning_threshold: int = Field(description="数据清洗时长阈值 (秒)")


class SettingsResponse(BaseModel):
    """获取配置响应"""
    settings: SettingItems
    message: str = "success"


class UpdateSettingsRequest(BaseModel):
    """更新配置请求 (部分更新)"""
    user_name: Optional[str] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    input_tokens_cost: Optional[float] = None
    output_tokens_cost: Optional[float] = None
    classification_mode: Optional[str] = None
    long_log_threshold: Optional[int] = None
    multi_purpose_app_names: Optional[List[str]] = None
    aw_db_path: Optional[str] = None
    lw_db_path: Optional[str] = None
    chat_db_path: Optional[str] = None
    data_cleaning_threshold: Optional[int] = None


class UpdateApiKeyRequest(BaseModel):
    """更新 API Key 请求"""
    api_key: str = Field(description="新的 API Key")


class UpdateApiKeyResponse(BaseModel):
    """更新 API Key 响应"""
    success: bool
    message: str
