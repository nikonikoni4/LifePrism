"""
Timeline 数据提供者

为 Timeline 模块提供专用的数据加载方法
"""
from lifewatch.storage import LWBaseDataProvider
from lifewatch.utils import get_logger

logger = get_logger(__name__)


class TimelineProvider(LWBaseDataProvider):
    """
    Timeline 模块专用数据提供者
    
    继承 LWBaseDataProvider，使用基类的 get_activity_logs 方法
    封装 Timeline 相关的数据加载逻辑
    """
    
    def get_timeline_events_by_date(self, date: str, channel: str = 'pc') -> list[dict]:
        """
        获取指定日期的时间线事件数据
        
        内部调用基类 get_activity_logs，封装为 timeline 专用格式
        
        Args:
            date: str, 日期（YYYY-MM-DD 格式）
            channel: str, 数据通道 ('pc' 或 'mobile'，当前仅支持 'pc')
        
        Returns:
            list[dict]: 事件列表
        """
        # 调用基类方法
        logs, _ = self.get_activity_logs(
            date=date,
            query_fields=["id", "start_time", "end_time", "duration", "app", "title", 
                         "category_id", "sub_category_id"],
            order_desc=False  # 升序
        )
        
        # 转换为 timeline 格式
        events = []
        for log in logs:
            events.append({
                "id": log.get("id"),
                "start_time": log.get("start_time"),
                "end_time": log.get("end_time"),
                "duration": log.get("duration"),
                "app": log.get("app"),
                "title": log.get("title"),
                "category_id": log.get("category_id") or "",
                "category_name": log.get("category_name") or "",
                "sub_category_id": log.get("sub_category_id") or "",
                "sub_category_name": log.get("sub_category_name") or "",
                "app_description": "",  # 保留字段
                "title_analysis": "",   # 保留字段
                "device_type": "pc"
            })
        
        return events
