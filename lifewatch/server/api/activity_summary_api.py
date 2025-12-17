"""
统计分析API路由
"""

from fastapi import APIRouter, Query, HTTPException
from datetime import date, timedelta
from typing import Optional
from lifewatch.server.schemas.activity_summary_schemas import ActivitySummaryResponse
from lifewatch.server.providers.statistical_data_providers import ServerLWDataProvider
from lifewatch.server.services.activity_summery_service import ActivitySummaryService

router = APIRouter(prefix="/activity-summary", tags=["ActivitySummary"])
# 初始化统计服务
activity_summary_service = ActivitySummaryService()


@router.get("", response_model=ActivitySummaryResponse, summary="获取活动总结数据")
async def get_activity_summary(
    date: str = Query(..., description="中心日期 (YYYY-MM-DD 格式)", regex=r"^\d{4}-\d{2}-\d{2}$"),
    history_number: int = Query(15, description="历史数据天数", ge=0, le=365),
    future_number: int = Query(14, description="未来数据天数", ge=0, le=365),
    category_id: Optional[str] = Query(None, description="主分类ID筛选（可选）"),
    sub_category_id: Optional[str] = Query(None, description="子分类ID筛选（可选）")
):
    """
    获取活动总结数据
    
    **功能：**
    - 获取指定日期为中心的活动数据摘要
    - 包含历史天数和未来天数的数据
    - 支持按主分类和子分类筛选
    - 用于ActivitySummaryHeader组件的迷你趋势图
    
    **参数：**
    - date: 中心日期 (YYYY-MM-DD格式)
    - history_number: 历史数据天数 (默认15天)
    - future_number: 未来数据天数 (默认14天)
    - category_id: 主分类ID筛选（可选）
    - sub_category_id: 子分类ID筛选（可选）
    
    **返回数据：**
    - DaylyActivities: 每日活动数据数组，包含日期、活动时长占比和分类颜色
    
    **示例：**
    - `/api/v1/activity-summary?date=2024-01-15&history_number=15&future_number=14`
    - `/api/v1/activity-summary?date=2024-01-15&category_id=work`
    - `/api/v1/activity-summary?date=2024-01-15&category_id=work&sub_category_id=coding`
    """
    try:
        # 调用服务方法获取数据（带分类筛选）
        data = activity_summary_service.get_activity_summary_data(
            date, history_number, future_number, category_id, sub_category_id
        )
        return data
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取活动总结失败: {str(e)}")

   
