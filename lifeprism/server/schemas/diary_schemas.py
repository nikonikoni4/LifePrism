"""
日记模块 Schema 定义

日记 meta 存数据库，内容存 md 文件。
模板纯文件管理，不经过数据库。
"""
from enum import Enum
from pydantic import BaseModel, Field
from typing import Optional, List


# ==================== 日记 ====================

class DiaryItem(BaseModel):
    """完整日记（meta + content），用于 GET 单条返回"""
    date: str = Field(..., description="日期 YYYY-MM-DD")
    mood: Optional[str] = Field(default=None, description="心情: very_happy, happy, calm, bad, very_bad")
    importance: Optional[str] = Field(default=None, description="平凡程度: important, normal, unimportant")
    custom_tags: List[str] = Field(default=[], description="自定义 tag 列表")
    word_count: int = Field(default=0, description="字数统计")
    ai_summary: Optional[str] = Field(default=None, description="AI 总结")
    diary_source_hash: Optional[str] = Field(default=None, description="当前 AI 总结对应的正文 hash")
    content: str = Field(default="", description="日记 md 内容")
    created_at: str = Field(default="", description="创建时间")
    updated_at: Optional[str] = Field(default=None, description="更新时间")


class DiaryMetaItem(BaseModel):
    """仅 meta（不含 content），用于日历列表"""
    date: str = Field(..., description="日期 YYYY-MM-DD")
    mood: Optional[str] = Field(default=None, description="心情")
    importance: Optional[str] = Field(default=None, description="平凡程度")
    custom_tags: List[str] = Field(default=[], description="自定义 tag 列表")
    word_count: int = Field(default=0, description="字数统计")
    ai_summary: Optional[str] = Field(default=None, description="AI 总结")
    diary_source_hash: Optional[str] = Field(default=None, description="当前 AI 总结对应的正文 hash")
    created_at: str = Field(default="", description="创建时间")
    updated_at: Optional[str] = Field(default=None, description="更新时间")


class DiaryListResponse(BaseModel):
    """日记列表响应"""
    items: List[DiaryMetaItem] = Field(default=[], description="日记 meta 列表")


class UpdateDiaryMetaRequest(BaseModel):
    """更新日记 meta（部分更新）"""
    mood: Optional[str] = Field(default=None, description="心情: very_happy, happy, calm, bad, very_bad")
    importance: Optional[str] = Field(default=None, description="平凡程度: important, normal, unimportant")
    custom_tags: Optional[List[str]] = Field(default=None, description="自定义 tag 列表")


class SaveDiaryContentRequest(BaseModel):
    """保存日记内容"""
    content: str = Field(..., description="日记 md 内容")


class DiaryAISummaryResponse(BaseModel):
    """日记 AI 总结响应"""
    content: str = Field(..., description="AI 生成的日记总结内容")


# ==================== AI 总结范围更新 ====================

class ExistingSummaryMode(str, Enum):
    """现有总结更新模式"""
    REGENERATE_ALL = "regenerate_all"
    REGENERATE_CHANGED = "regenerate_changed"
    SKIP_EXISTING = "skip_existing"


class GenerateDiaryAISummaryRangeRequest(BaseModel):
    """生成日记 AI 总结范围请求"""
    start_date: str = Field(..., description="开始日期 YYYY-MM-DD")
    end_date: str = Field(..., description="结束日期 YYYY-MM-DD")
    existing_summary_mode: ExistingSummaryMode = Field(..., description="现有总结更新模式")


class GenerateDiaryAISummaryRangeResponse(BaseModel):
    """生成日记 AI 总结范围响应"""
    created_dates: List[str] = Field(default=[], description="新建总结的日期列表")
    updated_dates: List[str] = Field(default=[], description="更新总结的日期列表")
    skipped_dates: List[str] = Field(default=[], description="跳过的日期列表")


# ==================== 模板 ====================

class TemplateItem(BaseModel):
    """模板详情"""
    name: str = Field(..., description="模板名称（文件名，不含 .md）")
    content: str = Field(default="", description="模板内容")


class TemplateListResponse(BaseModel):
    """模板列表响应"""
    items: List[str] = Field(default=[], description="模板名称列表")


class CreateTemplateRequest(BaseModel):
    """创建模板"""
    name: str = Field(..., description="模板名称")
    content: str = Field(default="", description="模板内容")


class UpdateTemplateRequest(BaseModel):
    """更新模板"""
    content: str = Field(..., description="模板内容")
