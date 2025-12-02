"""
仪表盘服务
提供仪表盘数据查询功能（当前使用 Mock 数据）
"""

import logging
from datetime import date, datetime
from typing import Dict, List, Any, Optional
from lifewatch.storage.lifewatch_data_manager import LifeWatchDataManager
from lifewatch.storage.database_manager import DatabaseManager
from lifewatch.config.database import DB_PATH

logger = logging.getLogger(__name__)

# 24小时分为12个时间段（每2小时）
TIME_RANGES = [
    "0-2", "2-4", "4-6", "6-8", "8-10", "10-12",
    "12-14", "14-16", "16-18", "18-20", "20-22", "22-24"
]


class DashboardService:
    """
    仪表盘数据服务
    
    TODO: 当前返回 Mock 数据，后续需要实现真实统计逻辑
    """
    
    def __init__(self, db_path: str = None):
        self.db = LifeWatchDataManager()
        # 为 Time Overview 使用 DatabaseManager
        if db_path is None:
            db_path = DB_PATH
        self.db_manager = DatabaseManager(db_path=db_path)
    
    def get_dashboard_data(self, target_date: date) -> Dict:
        """
        获取指定日期的仪表盘数据
        
        Args:
            target_date: 查询日期
            
        Returns:
            Dict: 仪表盘数据
        """
        # 第一阶段：返回 Mock 数据
        # return self._get_mock_dashboard_data(target_date)
        
        # 第二阶段：实现真实数据库查询
        return self._get_real_dashboard_data(target_date)
    
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
        4. 按 category 聚合统计
        5. 按 sub_category 聚合统计
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
    
    # ==================== Time Overview 功能 ====================
    
    def get_time_overview(self, date_str: str, parent_id: Optional[str] = None) -> Dict[str, Any]:
        """
        获取 Time Overview 数据
        
        Args:
            date_str: 日期字符串 (YYYY-MM-DD)
            parent_id: 可选，主分类ID（用于下钻到子分类）
            
        Returns:
            Dict: Time Overview 响应数据
        """
        try:
            # 1. 获取当天的行为日志
            logs_df = self._get_behavior_logs(date_str)
            
            if logs_df.empty:
                logger.warning(f"没有找到日期 {date_str} 的行为日志")
                return self._empty_response(parent_id)
            
            # 2. 根据 parent_id 决定聚合级别
            if parent_id is None:
                # 一级分类概览
                return self._build_main_category_overview(logs_df, date_str)
            else:
                # 二级分类详情
                return self._build_sub_category_details(logs_df, date_str, parent_id)
                
        except Exception as e:
            logger.error(f"获取 Time Overview 失败: {e}")
            raise
    
    def _get_behavior_logs(self, date_str: str) -> Any:
        """获取指定日期的行为日志"""
        start_time = f"{date_str} 00:00:00"
        end_time = f"{date_str} 23:59:59"
        
        # 使用 query 方法查询所有数据，然后用 pandas 过滤
        # 因为 DatabaseManager.query() 不支持范围查询
        logs_df = self.db_manager.query('user_app_behavior_log', order_by='start_time')
        
        # 使用 pandas 过滤日期范围
        if not logs_df.empty:
            logs_df = logs_df[
                (logs_df['start_time'] >= start_time) & 
                (logs_df['end_time'] <= end_time)
            ]
        
        return logs_df
    
    def _build_main_category_overview(self, logs_df: Any, date_str: str) -> Dict[str, Any]:
        """构建一级分类概览"""
        categories_df = self.db_manager.query('category', order_by='order_index ASC')
        
        category_times = {}
        for _, cat in categories_df.iterrows():
            cat_id = cat['id']
            cat_logs = logs_df[logs_df['category_id'] == cat_id]
            total_minutes = cat_logs['duration'].sum() / 60 if not cat_logs.empty else 0
            category_times[cat_id] = {
                'name': cat['name'],
                'color': cat['color'],
                'minutes': int(total_minutes)
            }
        
        pie_data = []
        bar_keys = []
        total_tracked = 0
        
        for cat_id, data in category_times.items():
            if data['minutes'] > 0:
                pie_data.append({
                    'key': cat_id,
                    'name': data['name'],
                    'value': data['minutes'],
                    'color': data['color']
                })
                bar_keys.append({
                    'key': cat_id,
                    'label': data['name'][:4],
                    'color': data['color']
                })
                total_tracked += data['minutes']
        
        bar_data = self._build_time_distribution(logs_df, list(category_times.keys()))
        
        return {
            'title': 'Time Overview',
            'subTitle': 'Activity breakdown & timeline',
            'totalTrackedMinutes': total_tracked,
            'pieData': pie_data,
            'barKeys': bar_keys,
            'barData': bar_data
        }
    
    def _build_sub_category_details(self, logs_df: Any, date_str: str, parent_id: str) -> Dict[str, Any]:
        """构建二级分类详情"""
        parent_cat = self.db_manager.get_by_id('category', 'id', parent_id)
        if not parent_cat:
            raise ValueError(f"分类 '{parent_id}' 不存在")
        
        sub_categories_df = self.db_manager.query(
            'sub_category',
            where={'category_id': parent_id},
            order_by='order_index ASC'
        )
        
        parent_logs = logs_df[logs_df['category_id'] == parent_id]
        
        sub_category_times = {}
        base_color = parent_cat['color']
        
        for idx, sub_cat in sub_categories_df.iterrows():
            sub_id = sub_cat['id']
            sub_logs = parent_logs[parent_logs['sub_category_id'] == sub_id]
            total_minutes = sub_logs['duration'].sum() / 60 if not sub_logs.empty else 0
            
            sub_color = self._generate_sub_color(base_color, idx, len(sub_categories_df))
            
            sub_category_times[sub_id] = {
                'name': sub_cat['name'],
                'color': sub_color,
                'minutes': int(total_minutes)
            }
        
        pie_data = []
        bar_keys = []
        total_tracked = 0
        
        for sub_id, data in sub_category_times.items():
            if data['minutes'] > 0:
                pie_data.append({
                    'key': sub_id,
                    'name': data['name'],
                    'value': data['minutes'],
                    'color': data['color']
                })
                bar_keys.append({
                    'key': sub_id,
                    'label': data['name'][:8],
                    'color': data['color']
                })
                total_tracked += data['minutes']
        
        bar_data = self._build_time_distribution(parent_logs, list(sub_category_times.keys()), is_sub=True)
        
        return {
            'title': f"{parent_cat['name']} Details",
            'subTitle': 'Detailed breakdown & timeline',
            'totalTrackedMinutes': total_tracked,
            'pieData': pie_data,
            'barKeys': bar_keys,
            'barData': bar_data
        }
    
    def _build_time_distribution(self, logs_df: Any, category_keys: List[str], is_sub: bool = False) -> List[Dict[str, Any]]:
        """构建24小时时间分布数据"""
        bar_data = []
        
        for time_range in TIME_RANGES:
            start_hour, end_hour = map(int, time_range.split('-'))
            time_slot = {'timeRange': time_range}
            
            for key in category_keys:
                if is_sub:
                    slot_logs = logs_df[
                        (logs_df['sub_category_id'] == key) &
                        (logs_df['start_time'].apply(lambda x: start_hour <= datetime.strptime(x, '%Y-%m-%d %H:%M:%S').hour < end_hour))
                    ]
                else:
                    slot_logs = logs_df[
                        (logs_df['category_id'] == key) &
                        (logs_df['start_time'].apply(lambda x: start_hour <= datetime.strptime(x, '%Y-%m-%d %H:%M:%S').hour < end_hour))
                    ]
                
                total_minutes = slot_logs['duration'].sum() / 60 if not slot_logs.empty else 0
                time_slot[key] = int(total_minutes)
            
            bar_data.append(time_slot)
        
        return bar_data

    
    def _generate_sub_color(self, base_color: str, index: int, total: int) -> str:
        """基于主色生成子分类渐变色"""
        if index == 0:
            return base_color
        
        r = int(base_color[1:3], 16)
        g = int(base_color[3:5], 16)
        b = int(base_color[5:7], 16)
        
        factor = 1 + (index / total) * 0.3
        r = min(255, int(r * factor))
        g = min(255, int(g * factor))
        b = min(255, int(b * factor))
        
        return f"#{r:02X}{g:02X}{b:02X}"
    
    def _empty_response(self, parent_id: Optional[str] = None) -> Dict[str, Any]:
        """返回空数据响应"""
        title = "Time Overview" if not parent_id else "Category Details"
        
        return {
            'title': title,
            'subTitle': 'No data available',
            'totalTrackedMinutes': 0,
            'pieData': [],
            'barKeys': [],
            'barData': [{'timeRange': tr} for tr in TIME_RANGES]
        }
if __name__ == "__main__":
    service = DashboardService()
    today = date.today().strftime("%Y-%m-%d")
        