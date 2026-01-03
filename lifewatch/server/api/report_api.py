"""
Report API - 报告接口

提供日报告和周报告的 RESTful API
"""
from fastapi import APIRouter, Query, HTTPException, Path

from lifewatch.server.schemas.report_schemas import (
    DailyReportResponse,
    DailyReportListResponse,
    WeeklyReportResponse,
)
from lifewatch.server.services.report_service import report_service, weekly_report_service
from lifewatch.server.providers.report_provider import report_provider, weekly_report_provider

router = APIRouter(prefix="/report", tags=["Report"])


# ============================================================================
# Daily Report 接口
# ============================================================================

@router.get("/daily", response_model=DailyReportResponse)
async def get_daily_report(
    date: str = Query(..., description="日期 YYYY-MM-DD"),
    force_refresh: bool = Query(default=False, description="是否强制重新计算数据")
):
    """
    获取日报告
    
    - 如果缓存存在且 state='1'，直接返回缓存数据
    - 否则重新计算所有板块数据并缓存
    - **force_refresh=True** 时强制重新计算，忽略缓存
    
    返回数据包含:
    - **sunburst_data**: 旭日图/时间分布数据
    - **todo_data**: Todo 完成统计
    - **goal_data**: Goal 进度追踪
    - **daily_trend_data**: 24小时时间趋势
    """
    return report_service.get_daily_report(date, force_refresh)


@router.delete("/daily/{date}")
async def delete_daily_report(
    date: str = Path(..., description="日期 YYYY-MM-DD")
):
    """
    删除日报告缓存
    
    删除指定日期的报告缓存，下次访问时会重新计算
    """
    success = report_provider.delete_daily_report(date)
    if not success:
        raise HTTPException(status_code=404, detail="报告不存在")
    return {"success": True}


@router.get("/daily/range", response_model=DailyReportListResponse)
async def get_daily_reports_in_range(
    start_date: str = Query(..., description="开始日期 YYYY-MM-DD"),
    end_date: str = Query(..., description="结束日期 YYYY-MM-DD")
):
    """
    获取日期范围内的日报告列表
    
    返回已缓存的报告数据，不会触发重新计算
    """
    reports = report_provider.get_reports_in_range(start_date, end_date)
    
    # 转换为响应模型
    items = []
    for report in reports:
        items.append(report_service._dict_to_response(report))
    
    return DailyReportListResponse(items=items, total=len(items))


@router.get("/daily/completed-dates")
async def get_completed_report_dates(
    start_date: str = Query(..., description="开始日期 YYYY-MM-DD"),
    end_date: str = Query(..., description="结束日期 YYYY-MM-DD")
):
    """
    获取日期范围内已完成的报告日期列表
    
    用于前端显示哪些日期有可用的报告数据
    """
    dates = report_provider.get_completed_report_dates(start_date, end_date)
    return {"dates": dates}


# ============================================================================
# Weekly Report 接口
# ============================================================================

@router.get("/weekly", response_model=WeeklyReportResponse)
async def get_weekly_report(
    week_start_date: str = Query(..., description="周开始日期 YYYY-MM-DD（周一）"),
    force_refresh: bool = Query(default=False, description="是否强制重新计算数据")
):
    """
    获取周报告
    
    - 如果缓存存在且 state='1'，直接返回缓存数据
    - 否则重新计算所有板块数据并缓存
    - **force_refresh=True** 时强制重新计算，忽略缓存
    
    返回数据包含:
    - **sunburst_data**: 旭日图/时间分布数据（整周聚合）
    - **todo_data**: Todo 完成统计（7天累计）
    - **goal_data**: Goal 进度追踪（整周）
    - **daily_trend_data**: 每日时间趋势（周一~周日）
    """
    return weekly_report_service.get_weekly_report(week_start_date, force_refresh)


@router.delete("/weekly/{week_start_date}")
async def delete_weekly_report(
    week_start_date: str = Path(..., description="周开始日期 YYYY-MM-DD（周一）")
):
    """
    删除周报告缓存
    
    删除指定周的报告缓存，下次访问时会重新计算
    """
    success = weekly_report_provider.delete_weekly_report(week_start_date)
    if not success:
        raise HTTPException(status_code=404, detail="周报告不存在")
    return {"success": True}


@router.get("/weekly/range")
async def get_weekly_reports_in_range(
    start_date: str = Query(..., description="开始日期 YYYY-MM-DD"),
    end_date: str = Query(..., description="结束日期 YYYY-MM-DD")
):
    """
    获取日期范围内的周报告列表
    
    返回已缓存的周报告数据，不会触发重新计算
    """
    reports = weekly_report_provider.get_reports_in_range(start_date, end_date)
    
    # 转换为响应模型
    items = []
    for report in reports:
        week_start = report.get('date', '')
        # 计算周结束日期
        from datetime import datetime, timedelta
        if week_start:
            start_dt = datetime.strptime(week_start, '%Y-%m-%d')
            week_end = (start_dt + timedelta(days=6)).strftime('%Y-%m-%d')
            items.append(weekly_report_service._dict_to_response(report, week_start, week_end))
    
    return {"items": items, "total": len(items)}

