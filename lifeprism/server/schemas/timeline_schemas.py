from pydantic import BaseModel, Field
from typing import List, Optional, Literal

# ============================================================================
# 非缩略图的 Timeline 数据显示
# ============================================================================
# 使用 activity_schemas.py 中的:
#   - ActivityLogItem: 单条日志
#   - ActivityLogDetailResponse: 日志详情
#   - ActivityLogsResponse: 日志列表


# ============================================================================
# 缩略图 Timeline Schemas
# ============================================================================

class TimelineCategoryStats(BaseModel):
    """单个分类在时间块内的统计数据"""
    id: str = Field(..., description="分类ID（主分类或子分类）")
    name: str = Field(..., description="分类名称")
    color: str = Field(..., description="分类颜色（十六进制格式）")
    duration: int = Field(..., description="该分类在此时间块内的持续时长（秒）")
    percentage: float = Field(..., description="占该时间块的百分比（0-100）")


class TimelineBlockStats(BaseModel):
    """单个时间块的统计数据（对应前端的 HourlyData）"""
    start_hour: int = Field(..., description="时间块开始小时（0-23）")
    end_hour: int = Field(..., description="时间块结束小时（1-24）")
    categories: List[TimelineCategoryStats] = Field(
        default=[], 
        description="该时间块内的分类统计（按时长降序排列）"
    )
    total_duration: int = Field(..., description="该时间块内的总活动时长（秒）")
    empty_duration: int = Field(..., description="该时间块内的空闲时长（秒）")
    empty_percentage: float = Field(..., description="空闲时间占比（0-100）")


class TimelineStatsResponse(BaseModel):
    """缩略图 Timeline 完整响应"""
    date: str = Field(..., description="查询日期（YYYY-MM-DD）")
    hour_granularity: int = Field(..., description="时间粒度（小时数：1/2/3/4/6）")
    category_level: Literal["main", "sub"] = Field(..., description="分类级别（主分类/子分类）")
    blocks: List[TimelineBlockStats] = Field(
        default=[], 
        description="时间块列表（按小时顺序排列）"
    )
    total_tracked_duration: int = Field(..., description="当日总追踪时长（秒）")


# ============================================================================
# 缩略图点击后的 Time Overview
# ============================================================================
from lifeprism.server.schemas.activity_schemas import TimeOverviewData

class TimelineTimeOverviewResponse(BaseModel):
    """点击缩略图时间块后的详细概览"""
    data: TimeOverviewData = Field(..., description="缩略图的 Time Overview")

# ============================================================================
# 用户的自定义添加数据，备注
# ============================================================================

class UserCustomBlockCreate(BaseModel):
    """创建用户自定义数据块的请求体
    
    前端传入分类 ID，后端存储 ID 到数据库
    分类和 todo_id 均为可选项
    """
    content: str = Field(..., description="活动内容描述")
    start_time: str = Field(..., description="开始时间（ISO格式：YYYY-MM-DDTHH:MM:SS）")
    end_time: str = Field(..., description="结束时间（ISO格式：YYYY-MM-DDTHH:MM:SS）")
    duration: int = Field(..., description="持续时长（分钟）")
    category_id: Optional[str] = Field(None, description="主分类ID（可选）")
    sub_category_id: Optional[str] = Field(None, description="子分类ID（可选）")
    todo_id: Optional[int] = Field(None, description="关联的待办事项ID（可选）")
    color: Optional[str] = Field(None, description="活动颜色（可选，前端随机生成 Tailwind 200 系列）")
    

class UserCustomBlockUpdate(BaseModel):
    """更新用户自定义数据块的请求体（所有字段可选）"""
    content: Optional[str] = Field(None, description="活动内容描述")
    start_time: Optional[str] = Field(None, description="开始时间（ISO格式：YYYY-MM-DDTHH:MM:SS）")
    end_time: Optional[str] = Field(None, description="结束时间（ISO格式：YYYY-MM-DDTHH:MM:SS）")
    duration: Optional[int] = Field(None, description="持续时长（分钟）")
    category_id: Optional[str] = Field(None, description="主分类ID")
    sub_category_id: Optional[str] = Field(None, description="子分类ID")
    todo_id: Optional[int] = Field(None, description="关联的待办事项ID")
    color: Optional[str] = Field(None, description="活动颜色")


class UserCustomBlock(BaseModel):
    """用户自定义数据块 - 完整模型（返回给前端）
    
    注意：
    - 分类字段为可选，如果未设置会返回 None
    - todo_content 为绑定的待办事项内容
    - color 由前端随机生成并存储
    """
    id: int = Field(..., description="数据块ID")
    content: str = Field(..., description="活动内容描述")
    todo_id: Optional[int] = Field(None, description="关联的待办事项ID")
    todo_content: Optional[str] = Field(None, description="关联的待办事项内容（由后端查询填充）")
    start_time: str = Field(..., description="开始时间（ISO格式：YYYY-MM-DDTHH:MM:SS）")
    end_time: str = Field(..., description="结束时间（ISO格式：YYYY-MM-DDTHH:MM:SS）")
    duration: int = Field(..., description="持续时长（分钟）")
    category_id: Optional[str] = Field(None, description="主分类ID")
    sub_category_id: Optional[str] = Field(None, description="子分类ID")
    category: Optional[str] = Field(None, description="主分类名称")
    sub_category: Optional[str] = Field(None, description="子分类名称")
    color: Optional[str] = Field(None, description="活动颜色（Tailwind 200 系列）")
    created_at: Optional[str] = Field(None, description="创建时间")
    updated_at: Optional[str] = Field(None, description="更新时间")


class UserCustomBlockResponse(BaseModel):
    """单条用户自定义数据块响应"""
    data: UserCustomBlock = Field(..., description="用户自定义数据块")


class UserCustomBlockListResponse(BaseModel):
    """用户自定义数据块列表响应"""
    data: List[UserCustomBlock] = Field(default=[], description="用户自定义数据块列表")
    total: int = Field(default=0, description="总数量")

