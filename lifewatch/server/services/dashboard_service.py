"""
仪表盘服务
提供仪表盘数据查询功能（当前使用 Mock 数据）
"""

from datetime import date, datetime
from typing import Dict
from lifewatch.storage.lifewatch_data_manager import LifeWatchDataManager


class DashboardService:
    """
    仪表盘数据服务
    
    TODO: 当前返回 Mock 数据，后续需要实现真实统计逻辑
    """
    
    def __init__(self):
        self.db = LifeWatchDataManager()
    
    def get_dashboard_data(self, target_date: date) -> Dict:
        """
        获取指定日期的仪表盘数据
        
        Args:
            target_date: 查询日期
            
        Returns:
            Dict: 仪表盘数据
        """
        # 第一阶段：返回 Mock 数据
        return self._get_mock_dashboard_data(target_date)
        
        # 第二阶段：实现真实数据库查询
        # return self._get_real_dashboard_data(target_date)
    
    def _get_mock_dashboard_data(self, target_date: date) -> Dict:
        """
        返回固定的 Mock 数据用于前端开发和API测试
        
        Args:
            target_date: 查询日期
            
        Returns:
            Dict: Mock 仪表盘数据
        """
        return {
            "date": target_date,
            "total_active_time": 10800,  # 3小时
            "summary": {
                "top_apps": [
                    {"name": "chrome.exe", "duration": 4500, "percentage": 41.7},
                    {"name": "code.exe", "duration": 3600, "percentage": 33.3},
                    {"name": "msedge.exe", "duration": 2700, "percentage": 25.0}
                ],
                "top_titles": [
                    {"name": "LifeWatch-AI - database_manager.py", "duration": 3600, "percentage": 33.3},
                    {"name": "Google - YouTube", "duration": 2400, "percentage": 22.2},
                    {"name": "GitHub - LifeWatch-AI", "duration": 2100, "percentage": 19.4},
                    {"name": "Stack Overflow - Python Questions", "duration": 1500, "percentage": 13.9},
                    {"name": "Bilibili - 技术视频", "duration": 1200, "percentage": 11.1}
                ],
                "categories_by_default": [
                    {"category": "工作/学习", "duration": 7200, "percentage": 66.7},
                    {"category": "生活/娱乐", "duration": 3600, "percentage": 33.3},
                    {"category": "其他", "duration": 0, "percentage": 0}
                ],
                "categories_by_goals": [
                    {"category": "编写LifeWatch-AI项目(代码)", "duration": 5400, "percentage": 50.0},
                    {"category": "其他", "duration": 5400, "percentage": 50.0}
                ]
            }
        }
    
    def _get_real_dashboard_data(self, target_date: date) -> Dict:
        """
        从数据库查询真实数据并统计
        
        实现步骤：
        1. 查询指定日期的所有行为日志
        2. 按 app 聚合统计时长
        3. 按 title 聚合统计时长  
        4. 按 class_by_default 聚合统计
        5. 按 class_by_goals 聚合统计
        6. 计算百分比
        7. 返回格式化数据
        
        Args:
            target_date: 查询日期
            
        Returns:
            Dict: 真实仪表盘数据
        """
        # TODO: 第二阶段实现
        start_time = f"{target_date} 00:00:00"
        end_time = f"{target_date} 23:59:59"
        
        # 查询该日期的所有行为日志
        logs_df = self.db.load_user_app_behavior_log(
            start_time=start_time,
            end_time=end_time
        )
        
        if logs_df is None or logs_df.empty:
            return {
                "date": target_date,
                "total_active_time": 0,
                "summary": {
                    "top_apps": [],
                    "top_titles": [],
                    "categories_by_default": [],
                    "categories_by_goals": []
                }
            }
        
        # TODO: 实现统计逻辑
        # - 总时长计算
        # - Top Apps 排序
        # - Top Titles 排序
        # - 分类统计和百分比计算
        
        pass
