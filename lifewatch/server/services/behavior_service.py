"""
行为日志服务
提供行为日志查询和时间线数据功能
"""

from datetime import date, datetime, timedelta
from typing import Dict, List, Optional
from lifewatch.server.providers.statistical_data_providers import ServerLWDataProvider


class BehaviorService:
    """
    行为日志数据服务
    
    提供行为日志查询、时间线数据等功能
    """
    
    def __init__(self):
        self.db = ServerLWDataProvider()
    
    def get_behavior_logs(
        self,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        app: Optional[str] = None,
        page: int = 1,
        page_size: int = 50
    ) -> Dict:
        """
        获取行为日志列表（分页）
        
        Args:
            start_time: 起始时间
            end_time: 结束时间
            app: 应用过滤
            page: 页码
            page_size: 每页大小
            
        Returns:
            Dict: 分页的行为日志数据
        """
        # 第一阶段：返回 Mock 数据
        return self._get_mock_behavior_logs(page, page_size)
        
        # 第二阶段：实现真实查询
        # return self._get_real_behavior_logs(start_time, end_time, app, page, page_size)
    
    def get_timeline(
        self,
        target_date: date,
        interval: str = "1h"
    ) -> Dict:
        """
        获取时间线数据
        
        Args:
            target_date: 查询日期
            interval: 时间间隔（1h, 30m, 15m）
            
        Returns:
            Dict: 时间线数据
        """
        # 第一阶段：返回 Mock 数据
        return self._get_mock_timeline(target_date, interval)
        
        # 第二阶段：实现真实查询
        # return self._get_real_timeline(target_date, interval)
    
    def _get_mock_behavior_logs(self, page: int, page_size: int) -> Dict:
        """返回 Mock 行为日志数据"""
        mock_logs = [
            {
                "id": f"event_{i}",
                "start_time": datetime.now() - timedelta(hours=i),
                "end_time": datetime.now() - timedelta(hours=i) + timedelta(minutes=3 + i//6),
                "duration": 180 + (i * 10),
                "app": ["chrome.exe", "code.exe", "msedge.exe"][i % 3],
                "title": [
                    "LifeWatch Documentation",
                    "database_manager.py - VS Code",
                    "Google Search - Python",
                ][i % 3],
                "category": ["工作/学习", "工作/学习", "生活/娱乐"][i % 3],
                "sub_category": ["编写LifeWatch-AI项目(代码)", "编写LifeWatch-AI项目(代码)", "其他"][i % 3],
                "is_multipurpose_app": [1, 0, 1][i % 3]
            }
            for i in range(1, 11)  # 生成10条 Mock 数据
        ]
        
        # 模拟分页
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        page_data = mock_logs[start_idx:end_idx]
        
        return {
            "total": 312,  # Mock 总数
            "page": page,
            "page_size": page_size,
            "data": page_data
        }
    
    def _get_mock_timeline(self, target_date: date, interval: str) -> Dict:
        """返回 Mock 时间线数据"""
        base_time = datetime.combine(target_date, datetime.min.time())
        
        # 生成24小时的时间槽（按1小时间隔）
        timeline_slots = []
        for hour in range(8, 18):  # 模拟8点到18点的活动
            slot_time = base_time + timedelta(hours=hour)
            slot_end_time = slot_time + timedelta(hours=1 if hour % 2 == 0 else 0.5)
            timeline_slots.append({
                "start_time": slot_time,
                "end_time": slot_end_time,
                "duration": 3600 if hour % 2 == 0 else 1800,  # 交替使用1小时或30分钟
                "events": [
                    {
                        "app": ["code.exe", "chrome.exe", "msedge.exe"][hour % 3],
                        "title": f"工作内容 - {hour}:00",
                        "duration": 1800,
                        "category": "工作/学习" if hour < 17 else "生活/娱乐",
                        "sub_category": "编写LifeWatch-AI项目(代码)" if hour < 17 else "其他"
                    }
                ]
            })
        
        return {
            "date": target_date,
            "interval": interval,
            "timeline": timeline_slots
        }
    
    def _get_real_behavior_logs(
        self,
        start_time: Optional[str],
        end_time: Optional[str],
        app: Optional[str],
        page: int,
        page_size: int
    ) -> Dict:
        """
        从数据库查询真实行为日志
        
        TODO: 第二阶段实现
        - 使用 LifeWatchDataManager 查询数据
        - 实现分页逻辑
        - 应用过滤条件
        """
        pass
    
    def _get_real_timeline(self, target_date: date, interval: str) -> Dict:
        """
        从数据库查询并构建时间线数据
        
        TODO: 第二阶段实现
        - 查询指定日期的所有事件
        - 按时间间隔分组
        - 构建时间槽数据结构
        """
        pass
