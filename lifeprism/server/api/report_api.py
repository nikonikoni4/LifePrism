"""
Report API - 报告接口

提供日报告、周报告和月报告的 RESTful API
"""
from fastapi import APIRouter, Query, HTTPException, Path

from lifeprism.server.schemas.report_schemas import (
    DailyReportResponse,
    DailyReportListResponse,
    WeeklyReportResponse,
    MonthlyReportResponse,
    AISummaryResponse,
    AISummaryRequest,
    WeeklyAISummaryRequest,
    MonthlyAISummaryRequest,
    TokenUsage,
)
from lifeprism.server.services.report_service import (
    get_daily_report as service_get_daily_report,
    get_weekly_report as service_get_weekly_report,
    get_monthly_report as service_get_monthly_report,
    get_daily_ai_summary as service_get_daily_ai_summary,
    get_weekly_ai_summary as service_get_weekly_ai_summary,
    get_monthly_ai_summary as service_get_monthly_ai_summary,
    _daily_dict_to_response,
    _weekly_dict_to_response,
    _monthly_dict_to_response,
)
from lifeprism.server.providers.report_provider import daily_report_provider, weekly_report_provider, monthly_report_provider

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
    return service_get_daily_report(date, force_refresh)


@router.post("/daily/ai_summary", response_model=AISummaryResponse)
async def get_daily_ai_summary(
    request: AISummaryRequest
):
    """
    获取每日 AI 总结
    
    调用 LLM 生成每日活动的智能分析总结
    
    请求体参数:
    - **date**: 日期 YYYY-MM-DD
    - **pattern**: 总结模式（可选，默认 "complex"）
      - complex: 复杂模式，包含更多统计信息
      - simple: 简单模式，只包含基本统计信息
    
    返回:
    - **content**: AI 生成的总结内容
    - **tokens_usage**: Token 使用量统计
    """
    
    result = await service_get_daily_ai_summary(request.date, request.pattern)
    return AISummaryResponse(
        content=result['content'],
        tokens_usage=TokenUsage(
            input_tokens=result['tokens_usage']['input_tokens'],
            output_tokens=result['tokens_usage']['output_tokens'],
            total_tokens=result['tokens_usage']['total_tokens']
        )
    )


@router.get("/daily/range", response_model=DailyReportListResponse)
async def get_daily_reports_in_range(
    start_date: str = Query(..., description="开始日期 YYYY-MM-DD"),
    end_date: str = Query(..., description="结束日期 YYYY-MM-DD")
):
    """
    获取日期范围内的日报告列表
    
    返回已缓存的报告数据，不会触发重新计算
    """
    reports = daily_report_provider.get_reports_in_range(start_date, end_date)
    
    # 转换为响应模型
    items = []
    for report in reports:
        items.append(_daily_dict_to_response(report))
    
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
    dates = daily_report_provider.get_completed_report_dates(start_date, end_date)
    return {"dates": dates}


@router.delete("/daily/{date}")
async def delete_daily_report(
    date: str = Path(..., description="日期 YYYY-MM-DD")
):
    """
    删除日报告缓存
    
    删除指定日期的报告缓存，下次访问时会重新计算
    """
    success = daily_report_provider.delete_daily_report(date)
    if not success:
        raise HTTPException(status_code=404, detail="报告不存在")
    return {"success": True}


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
    return service_get_weekly_report(week_start_date, force_refresh)


@router.post("/weekly/ai_summary", response_model=AISummaryResponse)
async def get_weekly_ai_summary(
    request: WeeklyAISummaryRequest
):
    """
    获取周 AI 总结
    
    调用 LLM 生成每周活动的智能分析总结
    
    请求体参数:
    - **week_start_date**: 周开始日期 YYYY-MM-DD（周一）
    - **week_end_date**: 周结束日期 YYYY-MM-DD（周日）
    - **pattern**: 总结模式（可选，默认 "complex"）
    
    返回:
    - **content**: AI 生成的总结内容
    - **tokens_usage**: Token 使用量统计
    """
    result = await service_get_weekly_ai_summary(
        request.week_start_date, 
        request.week_end_date, 
        request.pattern
    )
    return AISummaryResponse(
        content=result['content'],
        tokens_usage=TokenUsage(
            input_tokens=result['tokens_usage']['input_tokens'],
            output_tokens=result['tokens_usage']['output_tokens'],
            total_tokens=result['tokens_usage']['total_tokens']
        )
    )


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
            items.append(_weekly_dict_to_response(report, week_start, week_end))
    
    return {"items": items, "total": len(items)}


# ============================================================================
# Monthly Report 接口
# ============================================================================

@router.get("/monthly", response_model=MonthlyReportResponse)
async def get_monthly_report(
    month: str = Query(..., description="月份 YYYY-MM"),
    force_refresh: bool = Query(default=False, description="是否强制重新计算数据")
):
    """
    获取月报告
    
    - 如果缓存存在且 state='1'，直接返回缓存数据
    - 否则重新计算所有板块数据并缓存
    - **force_refresh=True** 时强制重新计算，忽略缓存
    
    返回数据包含:
    - **sunburst_data**: 旭日图/时间分布数据（整月聚合）
    - **todo_data**: Todo 完成统计（整月累计）
    - **goal_data**: Goal 进度追踪（整月）
    - **daily_trend_data**: 每日时间趋势（1日~末日）
    - **heatmap_data**: 热力图数据（每日总分钟数和分类分解）
    """
    return service_get_monthly_report(month, force_refresh)


@router.post("/monthly/ai_summary", response_model=AISummaryResponse)
async def get_monthly_ai_summary(
    request: MonthlyAISummaryRequest
):
    """
    获取月 AI 总结
    
    调用 LLM 生成每月活动的智能分析总结
    
    请求体参数:
    - **month_start_date**: 月开始日期 YYYY-MM-01
    - **month_end_date**: 月结束日期 YYYY-MM-DD（月末）
    - **pattern**: 总结模式（可选，默认 "complex"）
    
    返回:
    - **content**: AI 生成的总结内容
    - **tokens_usage**: Token 使用量统计
    """
    result = await service_get_monthly_ai_summary(
        request.month_start_date, 
        request.month_end_date, 
        request.pattern
    )
    return AISummaryResponse(
        content=result['content'],
        tokens_usage=TokenUsage(
            input_tokens=result['tokens_usage']['input_tokens'],
            output_tokens=result['tokens_usage']['output_tokens'],
            total_tokens=result['tokens_usage']['total_tokens']
        )
    )


@router.delete("/monthly/{month_start_date}")
async def delete_monthly_report(
    month_start_date: str = Path(..., description="月开始日期 YYYY-MM-01")
):
    """
    删除月报告缓存
    
    删除指定月的报告缓存，下次访问时会重新计算
    """
    success = monthly_report_provider.delete_monthly_report(month_start_date)
    if not success:
        raise HTTPException(status_code=404, detail="月报告不存在")
    return {"success": True}


@router.get("/monthly/range")
async def get_monthly_reports_in_range(
    start_date: str = Query(..., description="开始日期 YYYY-MM-DD"),
    end_date: str = Query(..., description="结束日期 YYYY-MM-DD")
):
    """
    获取日期范围内的月报告列表
    
    返回已缓存的月报告数据，不会触发重新计算
    """
    import calendar
    from datetime import datetime
    
    reports = monthly_report_provider.get_reports_in_range(start_date, end_date)
    
    # 转换为响应模型
    items = []
    for report in reports:
        month_start = report.get('date', '')
        if month_start:
            # 计算月结束日期
            dt = datetime.strptime(month_start, '%Y-%m-%d')
            last_day = calendar.monthrange(dt.year, dt.month)[1]
            month_end = f"{dt.year}-{dt.month:02d}-{last_day:02d}"
            items.append(_monthly_dict_to_response(report, month_start, month_end))
    
    return {"items": items, "total": len(items)}
