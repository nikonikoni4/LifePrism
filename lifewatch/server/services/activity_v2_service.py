"""
Activity V2 Service 层

实现活动统计和日志管理的业务逻辑
"""

from datetime import datetime, timedelta
from typing import Optional, List

from lifewatch.server.schemas.activity_v2_schemas import (
    ActivityStatsIncludeOptions,
    ActivityStatsResponse,
    ActivityLogsResponse,
    ActivityLogItem,
)
from lifewatch.server.providers.statistical_data_providers import server_lw_data_provider
from lifewatch.server.services.activity_stats_builder import (
    build_activity_summary,
    build_time_overview,
    get_top_title,
    get_top_app,
    get_todolist,
)
from lifewatch.utils import get_logger

logger = get_logger(__name__)


class ActivityService:
    """活动管理服务"""
    
    def get_activity_stats(
        self,
        date: str,
        include_options: ActivityStatsIncludeOptions,
        history_number: int,
        future_number: int,
        category_id: Optional[str],
        sub_category_id: Optional[str]
    ) -> ActivityStatsResponse:
        """
        获取活动统计数据
        
        Args:
            date: 中心日期 (YYYY-MM-DD 格式)
            include_options: 包含选项（由 API 层解析后传入）
            history_number: 历史数据天数
            future_number: 未来数据天数
            category_id: 主分类ID筛选（可选）
            sub_category_id: 子分类ID筛选（可选）
            
        Returns:
            ActivityStatsResponse: 活动统计响应
        """
        result = ActivityStatsResponse(
            query={
                "date": date,
                "include_options": include_options.model_dump(),
                "history_number": history_number,
                "future_number": future_number,
                "category_id": category_id,
                "sub_category_id": sub_category_id
            }
        )
        
        # 根据 include 选项按需获取数据（调用纯函数模块）
        if include_options.include_activity_summary:
            result.activity_summary = build_activity_summary(
                date, history_number, future_number, category_id, sub_category_id
            )
        
        if include_options.include_time_overview:
            result.time_overview = build_time_overview(date)
        
        if include_options.include_top_title:
            result.top_title = get_top_title(date, top_n=5)
        
        if include_options.include_top_app:
            result.top_app = get_top_app(date, top_n=5)
        
        if include_options.include_todolist:
            result.todolist = get_todolist(date)
        
        return result
    
    # ========================================================================
    # 日志相关方法
    # ========================================================================
    
    def get_activity_logs(
        self,
        date: Optional[str],
        start_time: Optional[str],
        end_time: Optional[str],
        device_filter: str,
        category_id: Optional[str],
        sub_category_id: Optional[str],
        sort_by: Optional[str],
        sort_order: Optional[str],
        page: int,
        page_size: int
    ) -> ActivityLogsResponse:
        """
        获取活动日志列表
        
        支持按日期或时间范围查询，使用 provider 的统一查询方法
        
        Args:
            date: 查询日期 (YYYY-MM-DD 格式)，提供时查询整天数据
            start_time: 开始时间 (YYYY-MM-DD HH:MM:SS 格式)
            end_time: 结束时间 (YYYY-MM-DD HH:MM:SS 格式)
            device_filter: 设备过滤 (all/pc/mobile)，当前未使用
            category_id: 主分类ID筛选
            sub_category_id: 子分类ID筛选
            sort_by: 排序字段 (duration/start_time/app)
            sort_order: 排序方向 (asc/desc)
            page: 页码
            page_size: 每页数量
            
        Returns:
            ActivityLogsResponse: 日志列表响应
            
        Note:
            必须提供 date 或 (start_time 和 end_time) 之一
        """
        # 通过 provider 的统一方法获取数据
        logs, total = server_lw_data_provider.get_activity_logs(
            date=date,
            start_time=start_time,
            end_time=end_time,
            category_id=category_id,
            sub_category_id=sub_category_id,
            order_by=sort_by,
            order_desc=(sort_order == "desc"),
            page=page,
            page_size=page_size
        )
        
        # 转换为 ActivityLogItem 列表
        log_items = [
            ActivityLogItem(
                id=log["id"],
                start_time=log["start_time"],
                end_time=log["end_time"],
                app=log["app"],
                title=log["title"],
                duration=log["duration"],
                category_id=log.get("category_id"),
                sub_category_id=log.get("sub_category_id"),
                category=log.get("category_name"),
                sub_category=log.get("sub_category_name")
            )
            for log in logs
        ]
        
        return ActivityLogsResponse(
            data=log_items,
            total=total,
            page=page,
            page_size=page_size
        )
    
    def get_activity_log_detail(self, log_id: str) -> Optional[ActivityLogItem]:
        """
        获取单条日志详情
        
        Args:
            log_id: 日志ID
            
        Returns:
            ActivityLogItem: 日志详情，如果不存在返回 None
        """
        log = server_lw_data_provider.get_activity_log_by_id(log_id)
        
        if not log:
            return None
        
        return ActivityLogItem(
            id=log["id"],
            start_time=log["start_time"],
            end_time=log["end_time"],
            app=log["app"],
            title=log["title"],
            duration=log["duration"],
            category_id=log.get("category_id"),
            sub_category_id=log.get("sub_category_id"),
            category=log.get("category_name"),
            sub_category=log.get("sub_category_name")
        )
    
    def update_log_category(
        self,
        log_id: str,
        category_id: str,
        sub_category_id: Optional[str]
    ) -> bool:
        """更新日志分类"""
        # TODO: 实现业务逻辑
        return False
    
    def batch_update_log_category(
        self,
        log_ids: list,
        category_id: str,
        sub_category_id: Optional[str]
    ) -> int:
        """批量更新日志分类，返回更新数量"""
        # TODO: 实现业务逻辑
        return 0
