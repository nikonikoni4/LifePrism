"""
内置监控数据提供者 (Processor 专用)
"""
import logging
from datetime import datetime
from typing import List, Dict, Optional
from lifeprism.config import settings
from lifeprism.repository import LWBaseDataProvider

logger = logging.getLogger(__name__)

class ProcessorMonitorDataProvider(LWBaseDataProvider):
    """
    Processor 模块专用的内置监控数据提供者
    从 window_events 表读取数据，并转换为清洗组件预期的格式
    """

    def __init__(self, db_manager=None):
        super().__init__(db_manager)

    def get_window_events(
        self,
        start_time: datetime,
        end_time: datetime,
        limit: int = 500000
    ) -> List[Dict]:
        """
        获取内置监控的窗口事件

        Args:
            start_time: 开始时间 (datetime)
            end_time: 结束时间 (datetime)
            limit: 最大返回条数

        Returns:
            List[Dict]: 符合清洗组件预期格式的事件列表
        """
        query = """
            SELECT id, timestamp, duration, app, title
            FROM window_events
            WHERE timestamp >= ? AND timestamp <= ?
            ORDER BY timestamp ASC
            LIMIT ?
        """
        if settings.monitor_type != 'lifeprism':
            # activitywatch的格式
            start_str = start_time.strftime("%Y-%m-%dT%H:%M:%S") if isinstance(start_time, datetime) else start_time
            end_str = end_time.strftime("%Y-%m-%dT%H:%M:%S") if isinstance(end_time, datetime) else end_time
        else:
            # lifeprism的时间戳已经改为了YYYY-MM-DD HH:MM:SS
            start_str = start_time.strftime("%Y-%m-%d %H:%M:%S") if isinstance(start_time, datetime) else start_time
            end_str = end_time.strftime("%Y-%m-%d %H:%M:%S") if isinstance(end_time, datetime) else end_time
        params = [start_str, end_str, limit]

        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, params)
                rows = cursor.fetchall()

                events = []
                for row in rows:
                    # 转换为 EventTransformer 预期的 AW 格式
                    event = {
                        'id': row['id'],
                        'timestamp': row['timestamp'],
                        'duration': row['duration'],
                        'data': {
                            'app': row['app'],
                            'title': row['title']
                        }
                    }
                    events.append(event)

                return events
        except Exception as e:
            logger.error(f"获取内置监控事件失败: {e}")
            return []


if __name__ == "__main__":
    print(len(ProcessorMonitorDataProvider().get_window_events(start_time="2026-04-29 12:08:46" ,end_time="2026-04-30 01:01:00")))