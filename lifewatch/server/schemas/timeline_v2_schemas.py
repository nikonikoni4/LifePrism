from pydantic import BaseModel, Field
from typing import List, Optional, Literal

# ============================================================================
# 非缩略图的 Timeline 数据显示
# ============================================================================
# 使用 activity_v2_schemas.py 中的:
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
from lifewatch.server.schemas.activity_v2_schemas import TimeOverviewData

class TimelineTimeOverviewResponse(BaseModel):
    """点击缩略图时间块后的详细概览"""
    data: TimeOverviewData = Field(..., description="缩略图的 Time Overview")