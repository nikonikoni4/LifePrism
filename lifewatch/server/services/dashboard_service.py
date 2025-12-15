"""
仪表盘服务
提供仪表盘数据和时间概览功能
"""

from datetime import date, datetime, timedelta
from typing import Dict, Optional
import pandas as pd
from lifewatch.server.providers.statistical_data_providers import StatisticalDataProvider


class DashboardService:
    """
    仪表盘数据服务
    
    提供仪表盘总览数据、时间概览等功能
    """
    
    def __init__(self):
        self.db = StatisticalDataProvider()  # 现在使用 StatisticalDataProvider
        self.stat_provider = self.db  # 保持兼容性
    
    def get_dashboard_data(self, query_date: date) -> Dict:
        """
        获取指定日期的仪表盘数据
        
        Args:
            query_date: 查询日期
            
        Returns:
            Dict: 仪表盘数据，包括总活跃时长、Top应用、Top标题、分类统计
        """
        # 使用真实数据
        return self._get_real_dashboard_data(query_date)
        
        # Mock 数据（调试时可切换回来）
        # return self._get_mock_dashboard_data(query_date)
    
    def get_time_overview(self, date_str: str) -> Dict:
        """
        获取时间概览数据
        
        Args:
            date_str: 日期字符串 (YYYY-MM-DD)
            
        Returns:
            Dict: 时间概览数据，包括饼图、柱状图配置和24小时分布
        """
        # 使用真实数据查询
        return self._get_real_time_overview(date_str)
        
        # Mock 数据（如需要可以切换回来）
        # return self._get_mock_time_overview(date_str, parent_id)
    
    def get_homepage_data(self, date_str: str, history_days: int = 15, future_days: int = 14) -> Dict:
        """
        获取首页统一数据（整合三个API的数据）
        
        Args:
            date_str: 日期字符串 (YYYY-MM-DD)
            history_days: 活动总结历史天数（默认15天）
            future_days: 活动总结未来天数（默认14天）
            
        Returns:
            Dict: 包含 activity_summary、dashboard 和 time_overview 的统一数据
        """
        from datetime import datetime
        from lifewatch.server.services.activity_summery_service import ActivitySummaryService
        
        # 解析日期
        query_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        
        # 初始化 activity_summary 服务
        activity_summary_service = ActivitySummaryService()
        
        # 获取三部分数据
        activity_summary_data = activity_summary_service.get_activity_summary_data(
            date_str, history_days, future_days
        )
        dashboard_data = self.get_dashboard_data(query_date)
        time_overview_data = self.get_time_overview(date_str)
        
        # 整合返回
        return {
            "activity_summary": activity_summary_data,
            "dashboard": dashboard_data,
            "time_overview": time_overview_data
        }
    
    def _get_mock_dashboard_data(self, query_date: date) -> Dict:
        """返回 Mock 仪表盘数据"""
        return {
            "date": query_date,
            "total_active_time": 10800,  # 3小时（秒）
            "summary": {
                "top_apps": [
                    {"name": "chrome.exe", "duration": 4500, "percentage": 41.7},
                    {"name": "code.exe", "duration": 3600, "percentage": 33.3},
                    {"name": "msedge.exe", "duration": 2700, "percentage": 25.0},
                    {"name": "figma.exe", "duration": 1800, "percentage": 16.7},
                    {"name": "spotify.exe", "duration": 1200, "percentage": 11.1}
                ],
                "top_titles": [
                    {"name": "LifeWatch Documentation", "duration": 2400, "percentage": 22.2},
                    {"name": "database_manager.py - VS Code", "duration": 2100, "percentage": 19.4},
                    {"name": "Google Search - Python", "duration": 1800, "percentage": 16.7},
                    {"name": "Dashboard Design - Figma", "duration": 1500, "percentage": 13.9},
                    {"name": "Localhost:3000 - Development", "duration": 1200, "percentage": 11.1}
                ],
                "categories_by_default": [
                    {"category": "工作/学习", "duration": 7200, "percentage": 66.7},
                    {"category": "生活/娱乐", "duration": 3600, "percentage": 33.3}
                ],
                "categories_by_goals": [
                    {"category": "编写LifeWatch-AI项目(代码)", "duration": 5400, "percentage": 50.0},
                    {"category": "其他", "duration": 5400, "percentage": 50.0}
                ]
            }
        }
    
    def _get_mock_time_overview(self, date_str: str, parent_id: Optional[str] = None) -> Dict:
        """返回 Mock 时间概览数据"""
        
        # 一级分类数据
        if parent_id is None:
            return {
                "title": "Time Overview",
                "subTitle": "Activity breakdown & timeline",
                "totalTrackedMinutes": 780,
                "pieData": [
                    {"key": "work", "name": "Work/Study", "value": 480, "color": "#5B8FF9"},
                    {"key": "entertainment", "name": "Entertainment", "value": 200, "color": "#5AD8A6"},
                    {"key": "other", "name": "Other", "value": 100, "color": "#5D7092"}
                ],
                "barKeys": [
                    {"key": "work", "label": "Work", "color": "#5B8FF9"},
                    {"key": "entertainment", "label": "Entertainment", "color": "#5AD8A6"},
                    {"key": "other", "label": "Other", "color": "#5D7092"}
                ],
                "barData": [
                    {"timeRange": "0-2", "work": 0, "entertainment": 0, "other": 0},
                    {"timeRange": "2-4", "work": 0, "entertainment": 0, "other": 0},
                    {"timeRange": "4-6", "work": 0, "entertainment": 0, "other": 0},
                    {"timeRange": "6-8", "work": 30, "entertainment": 0, "other": 30},
                    {"timeRange": "8-10", "work": 120, "entertainment": 0, "other": 0},
                    {"timeRange": "10-12", "work": 100, "entertainment": 10, "other": 10},
                    {"timeRange": "12-14", "work": 60, "entertainment": 40, "other": 20},
                    {"timeRange": "14-16", "work": 90, "entertainment": 20, "other": 10},
                    {"timeRange": "16-18", "work": 80, "entertainment": 30, "other": 10},
                    {"timeRange": "18-20", "work": 0, "entertainment": 60, "other": 20},
                    {"timeRange": "20-22", "work": 0, "entertainment": 40, "other": 0},
                    {"timeRange": "22-24", "work": 0, "entertainment": 0, "other": 0}
                ]
            }
        
        # 二级分类数据（下钻示例：work分类）
        if parent_id == "work":
            return {
                "title": "Work/Study Details",
                "subTitle": "Detailed breakdown of work activities",
                "totalTrackedMinutes": 480,
                "pieData": [
                    {"key": "coding", "name": "Coding", "value": 300, "color": "#5B8FF9"},
                    {"key": "documentation", "name": "Documentation", "value": 120, "color": "#61DDAA"},
                    {"key": "meetings", "name": "Meetings", "value": 60, "color": "#F6BD16"}
                ],
                "barKeys": [
                    {"key": "coding", "label": "Coding", "color": "#5B8FF9"},
                    {"key": "documentation", "label": "Documentation", "color": "#61DDAA"},
                    {"key": "meetings", "label": "Meetings", "color": "#F6BD16"}
                ],
                "barData": [
                    {"timeRange": "0-2", "coding": 0, "documentation": 0, "meetings": 0},
                    {"timeRange": "2-4", "coding": 0, "documentation": 0, "meetings": 0},
                    {"timeRange": "4-6", "coding": 0, "documentation": 0, "meetings": 0},
                    {"timeRange": "6-8", "coding": 20, "documentation": 10, "meetings": 0},
                    {"timeRange": "8-10", "coding": 80, "documentation": 30, "meetings": 10},
                    {"timeRange": "10-12", "coding": 60, "documentation": 30, "meetings": 10},
                    {"timeRange": "12-14", "coding": 40, "documentation": 10, "meetings": 10},
                    {"timeRange": "14-16", "coding": 60, "documentation": 20, "meetings": 10},
                    {"timeRange": "16-18", "coding": 40, "documentation": 20, "meetings": 20},
                    {"timeRange": "18-20", "coding": 0, "documentation": 0, "meetings": 0},
                    {"timeRange": "20-22", "coding": 0, "documentation": 0, "meetings": 0},
                    {"timeRange": "22-24", "coding": 0, "documentation": 0, "meetings": 0}
                ]
            }
        
        # 未知父分类ID
        raise ValueError(f"Unknown parent_id: {parent_id}")
    
    def _get_real_dashboard_data(self, query_date: date) -> Dict:
        """
        从数据库查询真实仪表盘数据
        
        Args:
            query_date: 查询日期
            
        Returns:
            Dict: 仪表盘数据
        """
        
        # 获取基础数据
        total_time = self.stat_provider.get_active_time(query_date.strftime("%Y-%m-%d"))
        top_apps = self.stat_provider.get_top_applications(top_n=5)
        top_titles = self.stat_provider.get_top_title(top_n=5)
        category_stats = self.stat_provider.get_category_stats()
        
        # 格式化数据
        return {
            "date": query_date,
            "total_active_time": int(total_time),  # 转换为整数，匹配 schema
            "summary": {
                "top_apps": self._format_top_items(top_apps, total_time),
                "top_titles": self._format_top_items(top_titles, total_time),
                "categories_by_default": self._format_categories(category_stats, total_time),
                "categories_by_goals": []  # TODO: 后续实现目标分类统计
            }
        }
    
    def _format_top_items(self, items: list[dict], total_time: int) -> list[dict]:
        """
        格式化 Top 项目数据，添加百分比
        
        Args:
            items: 原始数据列表，每项包含 name 和 duration(秒)
            total_time: 总时长（秒）
            
        Returns:
            list[dict]: 格式化后的数据，包含 name, duration(秒), percentage
        """
        return [
            {
                "name": item["name"],
                "duration": int(item["duration"]),  # 转换为整数，匹配 schema
                "percentage": round(item["duration"] / total_time * 100, 1) if total_time > 0 else 0
            }
            for item in items
        ]
    
    def _format_duration(self, seconds: int) -> str:
        """
        将秒数转换为人类可读的时长格式
        
        Args:
            seconds: 秒数
            
        Returns:
            str: 格式化的时长，如 "2h 30m", "45m", "30s"
        """
        if seconds < 60:
            return f"{seconds}s"
        
        minutes = seconds // 60
        if minutes < 60:
            return f"{minutes}m"
        
        hours = minutes // 60
        remaining_minutes = minutes % 60
        
        if remaining_minutes == 0:
            return f"{hours}h"
        return f"{hours}h {remaining_minutes}m"
    
    def _format_categories(self, categories: list[dict], total_time: int) -> list[dict]:
        """
        格式化分类统计数据
        
        Args:
            categories: 原始分类数据
            total_time: 总时长（秒）
            
        Returns:
            list[dict]: 格式化后的分类数据
        """
        return [
            {
                "category": cat["name"],
                "duration": int(cat["duration"]),  # 转换为整数，匹配 schema
                "percentage": round(cat["duration"] / total_time * 100, 1) if total_time > 0 else 0
            }
            for cat in categories
        ]
    
    def _get_real_time_overview(self, date_str: str, parent_id: Optional[str] = None) -> Dict:
        """
        从数据库查询真实时间概览数据（包含完整层级结构）
        
        Args:
            date_str: 日期字符串 (YYYY-MM-DD)
            parent_id: (已弃用) 兼容性保留，不再使用
            
        Returns:
            Dict: 包含完整层级的时间概览数据
        """
        from datetime import datetime
        
        # 1. 准备数据
        target_date = datetime.strptime(date_str, "%Y-%m-%d")
        start_time = f"{date_str} 00:00:00"
        end_time = f"{date_str} 23:59:59"
        
        df = self.db.load_user_app_behavior_log(start_time=start_time, end_time=end_time)
        
        # 如果没有数据
        if df is None or df.empty:
            return self._build_empty_response(date_str)
            
        # 预计算时长
        df['start_dt'] = pd.to_datetime(df['start_time'])
        df['end_dt'] = pd.to_datetime(df['end_time'])
        df['duration_minutes'] = (df['end_dt'] - df['start_dt']).dt.total_seconds() / 60
        
        # 加载颜色映射
        color_map = self._load_color_map()
        
        # 2. 构建 Level 1 (Category)
        root_data = self._build_view_data(
            df, 
            group_field='category', 
            title="Time Overview", 
            sub_title="Activity breakdown & timeline",
            color_map=color_map
        )
        
        root_data['details'] = {}
        
        # 获取所有一级分类
        categories = df['category'].unique()
        
        for category in categories:
            if pd.isna(category): continue
            
            # 过滤当前分类数据
            cat_df = df[df['category'] == category]
            if cat_df.empty: continue
            
            # 3. 构建 Level 2 (Sub-category)
            # 为子分类生成同色系颜色
            cat_color = color_map.get(category, "#5B8FF9")
            sub_categories = cat_df['sub_category'].unique()
            sub_colors = self._generate_color_variants(cat_color, len(sub_categories))
            sub_color_map = {sub: color for sub, color in zip(sub_categories, sub_colors)}
            
            cat_data = self._build_view_data(
                cat_df,
                group_field='sub_category',
                title=f"{category} Details",
                sub_title=f"Detailed breakdown of {category}",
                color_map=sub_color_map
            )
            
            cat_data['details'] = {}
            root_data['details'][category] = cat_data
            
            # 4. 构建 Level 3 (Apps)
            for sub_cat in sub_categories:
                if pd.isna(sub_cat): continue
                
                sub_df = cat_df[cat_df['sub_category'] == sub_cat]
                if sub_df.empty: continue
                
                # 应用级别的特殊处理（Top 5 + Other）
                app_data = self._build_app_level_data(
                    sub_df,
                    title=f"{sub_cat} Apps",
                    sub_title=f"Top applications in {sub_cat}",
                    base_color=sub_color_map.get(sub_cat, cat_color)
                )
                
                cat_data['details'][sub_cat] = app_data
                
        return root_data

    def _build_empty_response(self, date_str: str) -> Dict:
        return {
            "title": "Time Overview",
            "subTitle": f"No activity data for {date_str}",
            "totalTrackedMinutes": 0,
            "pieData": [],
            "barKeys": [],
            "barData": self._get_empty_bar_data(),
            "details": {}
        }

    def _load_color_map(self) -> Dict[str, str]:
        """加载分类颜色映射"""
        category_df = self.db.load_categories()
        color_map = {}
        if category_df is not None and not category_df.empty:
            for _, row in category_df.iterrows():
                color_map[row['name']] = row['color']
        return color_map

    def _build_view_data(self, df, group_field: str, title: str, sub_title: str, color_map: Dict) -> Dict:
        """构建标准视图数据（饼图 + 柱状图）"""
        # 聚合数据
        stats = df.groupby(group_field)['duration_minutes'].sum().to_dict()
        total_minutes = sum(stats.values())
        
        pie_data = []
        bar_keys = []
        
        # 排序并构建图表数据
        for name, minutes in sorted(stats.items(), key=lambda x: x[1], reverse=True):
            if pd.isna(name): name = "Uncategorized"
            color = color_map.get(name, "#E8684A")
            
            pie_data.append({
                "key": name,
                "name": name,
                "value": int(minutes),
                "color": color
            })
            
            bar_keys.append({
                "key": name,
                "label": name,
                "color": color
            })
            
        bar_data = self._calculate_time_distribution(df, group_field)
        
        return {
            "title": title,
            "subTitle": sub_title,
            "totalTrackedMinutes": int(total_minutes),
            "pieData": pie_data,
            "barKeys": bar_keys,
            "barData": bar_data
        }

    def _build_app_level_data(self, df, title: str, sub_title: str, base_color: str) -> Dict:
        """构建应用级别数据（Top 5 + Other）"""
        # 按应用分组
        stats = df.groupby('app')['duration_minutes'].sum().sort_values(ascending=False)
        total_minutes = stats.sum()
        
        # 取 Top 5
        top_5 = stats.head(5)
        other_value = stats.iloc[5:].sum()
        
        # 生成颜色
        colors = self._generate_color_variants(base_color, len(top_5) + (1 if other_value > 0 else 0))
        
        pie_data = []
        bar_keys = []
        
        # 处理 Top 5
        for i, (app_name, minutes) in enumerate(top_5.items()):
            color = colors[i]
            pie_data.append({
                "key": app_name,
                "name": app_name,
                "value": int(minutes),
                "color": color
            })
            bar_keys.append({
                "key": app_name,
                "label": app_name,
                "color": color
            })
            
        # 处理 Other
        if other_value > 0:
            other_color = colors[-1]
            pie_data.append({
                "key": "Other",
                "name": "Other Apps",
                "value": int(other_value),
                "color": other_color
            })
            bar_keys.append({
                "key": "Other",
                "label": "Other",
                "color": other_color
            })
            
        # 重新计算 bar_data (需要处理 Other 的合并)
        # 这里需要特殊的 _calculate_app_time_distribution
        bar_data = self._calculate_app_time_distribution(df, top_5.index.tolist())
        
        return {
            "title": title,
            "subTitle": sub_title,
            "totalTrackedMinutes": int(total_minutes),
            "pieData": pie_data,
            "barKeys": bar_keys,
            "barData": bar_data
        }

    def _calculate_app_time_distribution(self, df, top_apps: list) -> list:
        """计算应用级别的24小时分布（处理 Other）"""
        from collections import defaultdict
        time_slots = defaultdict(lambda: defaultdict(int))
        
        for _, row in df.iterrows():
            app_name = row['app']
            # 如果不在 Top 5，归为 Other
            key = app_name if app_name in top_apps else "Other"
            
            start = row['start_dt']
            end = row['end_dt']
            
            for hour in range(0, 24, 2):
                slot_start = start.replace(hour=hour, minute=0, second=0, microsecond=0)
                slot_end = slot_start + timedelta(hours=2)
                overlap_start = max(start, slot_start)
                overlap_end = min(end, slot_end)
                
                if overlap_start < overlap_end:
                    minutes = (overlap_end - overlap_start).total_seconds() / 60
                    time_slots[hour][key] += minutes
                    
        bar_data = []
        for hour in range(0, 24, 2):
            slot_data = {"timeRange": f"{hour}-{hour+2}"}
            for key, minutes in time_slots[hour].items():
                slot_data[key] = int(minutes)
            bar_data.append(slot_data)
            
        return bar_data

    def _generate_color_variants(self, base_color: str, count: int) -> list[str]:
        """
        基于基础颜色生成同色系配色方案
        
        Args:
            base_color: 基础颜色 (Hex)
            count: 需要生成的颜色数量
            
        Returns:
            list[str]: 颜色列表 (Hex)
        """
        import colorsys
        
        # 处理 Hex 格式
        if base_color.startswith('#'):
            base_color = base_color[1:]
        
        if len(base_color) != 6:
            # 格式错误回退
            return [f"#{base_color}"] * count if base_color else ["#5B8FF9"] * count
            
        try:
            r = int(base_color[0:2], 16) / 255.0
            g = int(base_color[2:4], 16) / 255.0
            b = int(base_color[4:6], 16) / 255.0
        except ValueError:
            return ["#5B8FF9"] * count
        
        h, l, s = colorsys.rgb_to_hls(r, g, b)
        
        colors = []
        
        if count <= 1:
            return [f"#{base_color}"]
            
        # 生成亮度变化
        # 保持色相(H)和饱和度(S)基本不变，调整亮度(L)
        # 亮度范围控制在 0.3 (深) 到 0.85 (浅) 之间
        # 基础颜色的亮度也应该在其中
        
        for i in range(count):
            # 简单的线性分布
            # 最大的块（i=0）使用接近基础颜色的亮度，或者稍微深一点
            # 越小的块越浅（或者反过来）
            
            # 这里采用从深到浅的分布，让大块颜色更重
            # 映射 i (0..count-1) 到 0.35..0.85
            
            # 动态调整范围，避免颜色太接近
            min_l = 0.35
            max_l = 0.85
            
            if count > 1:
                new_l = min_l + (max_l - min_l) * (i / (count - 1))
            else:
                new_l = l
                
            # 稍微调整饱和度，越亮越低饱和度，看起来更自然
            new_s = s * (1 - 0.2 * (i / count)) 
            
            r_new, g_new, b_new = colorsys.hls_to_rgb(h, new_l, new_s)
            
            # 转换为 Hex
            hex_color = "#{:02x}{:02x}{:02x}".format(
                int(max(0, min(1, r_new)) * 255),
                int(max(0, min(1, g_new)) * 255),
                int(max(0, min(1, b_new)) * 255)
            )
            colors.append(hex_color)
            
        return colors
    
    def _get_empty_bar_data(self) -> list:
        """生成空的24小时分布数据"""
        return [
            {"timeRange": f"{h}-{h+2}"} 
            for h in range(0, 24, 2)
        ]
    
    def _calculate_time_distribution(self, df, group_field: str) -> list:
        """
        计算24小时分布数据（按2小时间隔）
        
        Args:
            df: 行为日志DataFrame
            group_field: 分类字段（category 或 sub_category）
            
        Returns:
            list: 24小时分布数据
        """
        from collections import defaultdict
        
        # 初始化24小时的时间槽（每2小时一个）
        time_slots = defaultdict(lambda: defaultdict(int))
        
        for _, row in df.iterrows():
            start = row['start_dt']
            end = row['end_dt']
            category = row[group_field]
            
            if category is None or pd.isna(category):
                category = "Uncategorized"
            
            # 直接使用分类名称作为 key
            key = category
            
            # 计算该事件在每个2小时时间槽中的时长
            for hour in range(0, 24, 2):
                slot_start = start.replace(hour=hour, minute=0, second=0, microsecond=0)
                slot_end = slot_start + timedelta(hours=2)
                
                # 计算该事件与时间槽的重叠部分
                overlap_start = max(start, slot_start)
                overlap_end = min(end, slot_end)
                
                if overlap_start < overlap_end:
                    overlap_minutes = (overlap_end - overlap_start).total_seconds() / 60
                    time_slots[hour][key] += overlap_minutes
        
        # 构建柱状图数据
        bar_data = []
        for hour in range(0, 24, 2):
            time_range = f"{hour}-{hour+2}"
            slot_data = {"timeRange": time_range}
            
            # 添加每个分类的时长
            for key, minutes in time_slots[hour].items():
                slot_data[key] = int(minutes)
            
            bar_data.append(slot_data)
        
        return bar_data
    

    def _get_color_for_category(self, key: str, colors: dict) -> str:
        """
        智能获取分类的颜色，支持模糊匹配
        
        Args:
            key: 分类key
            colors: 颜色映射字典
            
        Returns:
            str: 颜色代码
        """
        # 精确匹配
        if key in colors:
            return colors[key]
        
        # 模糊匹配：检查是否包含关键词
        key_lower = key.lower()
        if "work" in key_lower or "工作" in key_lower:
            return colors.get("work", "#5B8FF9")
        if "study" in key_lower or "学习" in key_lower:
            return colors.get("study", "#61DDAA")
        if "entertainment" in key_lower or "娱乐" in key_lower:
            return colors.get("entertainment", "#5AD8A6")
        if "life" in key_lower or "生活" in key_lower:
            return colors.get("life", "#F6BD16")
        if "coding" in key_lower or "编程" in key_lower or "代码" in key_lower:
            return colors.get("coding", "#5B8FF9")
        
        # 返回默认颜色
        return colors.get("default", "#E8684A")
