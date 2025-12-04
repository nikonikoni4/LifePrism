"""
Timeline 数据服务层
处理时间线数据的业务逻辑和数据转换
"""

from datetime import datetime
from typing import List, Optional
from lifewatch.server.providers.statistical_data_providers import StatisticalDataProvider
from lifewatch.server.schemas.timeline_schemas import TimelineEventSchema, TimelineResponse


class TimelineService:
    """Timeline 服务类"""
    
    def __init__(self):
        self.data_provider = StatisticalDataProvider()
    
    def get_timeline_events(self, date: str, device_filter: str = 'all') -> TimelineResponse:
        """
        获取指定日期的时间线数据
        
        Args:
            date: 日期字符串，格式：YYYY-MM-DD
            device_filter: 设备过滤器 ('all', 'pc', 'mobile')
        
        Returns:
            TimelineResponse: 时间线响应数据
        """
        # TODO: 未来根据 device_filter 参数合并多个数据源
        # 当前阶段仅实现 PC 端数据
        channel = 'pc' if device_filter in ['all', 'pc'] else 'mobile'
        
        # 从数据提供者获取原始事件数据
        raw_events = self.data_provider.get_timeline_events_by_date(date, channel)
        
        # 转换为前端需要的格式
        events = []
        for event in raw_events:
            # 组装 description：app_description + title_description
            description_parts = []
            if event.get("app_description"):
                description_parts.append(event["app_description"])
            if event.get("title_description"):
                description_parts.append(event["title_description"])
            description = " - ".join(description_parts) if description_parts else event.get("title", "")
            
            # 将ISO timestamp转换为小时浮点数
            start_hour = self._time_to_hour_float(event["start_time"], date)
            end_hour = self._time_to_hour_float(event["end_time"], date)
            
            events.append(TimelineEventSchema(
                id=event["id"],
                start_time=start_hour,
                end_time=end_hour,
                title=event["title"],
                category=event["category_id"],
                category_name=event["category_name"],
                sub_category_id=event["sub_category_id"] if event["sub_category_id"] else None,
                sub_category_name=event["sub_category_name"] if event["sub_category_name"] else None,
                description=description,
                device_type=event["device_type"]
            ))
        
        # 计算当前时间（如果是今天）
        current_time = None
        today = datetime.now().strftime("%Y-%m-%d")
        if date == today:
            now = datetime.now()
            current_time = now.hour + now.minute / 60.0
        
        return TimelineResponse(
            date=date,
            events=events,
            current_time=current_time
        )
    
    def _time_to_hour_float(self, time_str: str, date_str: str) -> float:
        """
        将时间字符串转换为当天的小时浮点数
        
        Args:
            time_str: 时间字符串，格式：YYYY-MM-DD HH:MM:SS
            date_str: 日期字符串，格式：YYYY-MM-DD
        
        Returns:
            float: 小时数，如 9.5 表示 09:30
        """
        try:
            # 解析时间字符串
            dt = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
            # 提取小时和分钟
            hour = dt.hour
            minute = dt.minute
            return hour + minute / 60.0
        except Exception as e:
            # 如果解析失败，返回 0
            print(f"时间解析错误: {time_str}, 错误: {e}")
            return 0.0
