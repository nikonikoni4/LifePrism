"""
Timeline 数据服务层
处理时间线数据的业务逻辑和数据转换
"""

from datetime import datetime
from typing import List, Optional
from lifewatch.server.providers.statistical_data_providers import ServerLWDataProvider
from lifewatch.server.schemas.timeline_schemas import TimelineEventSchema, TimelineResponse
from lifewatch.server.services.category_color_manager import color_manager


class TimelineService:
    """Timeline 服务类"""
    
    def __init__(self):
        self.data_provider = ServerLWDataProvider()
    
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
            # 组装 description：app_description + title_analysis
            description_parts = []
            if event.get("app_description"):
                description_parts.append(event["app_description"])
            if event.get("title_analysis"):
                description_parts.append(event["title_analysis"])
            description = " - ".join(description_parts) if description_parts else event.get("title", "")
            
            # 将ISO timestamp转换为小时浮点数
            start_hour = self._time_to_hour_float(event["start_time"], date)
            end_hour = self._time_to_hour_float(event["end_time"], date)
            
            # 获取分类颜色
            category_color = color_manager.get_main_category_color(event["category_id"])
            sub_category_color = None
            if event["sub_category_id"]:
                sub_category_color = color_manager.get_sub_category_color(event["sub_category_id"])
            
            events.append(TimelineEventSchema(
                id=event["id"],
                start_time=start_hour,
                end_time=end_hour,
                title=event["title"],
                app=event["app"],
                category=event["category_id"],
                category_name=event["category_name"],
                category_color=category_color,
                sub_category_id=event["sub_category_id"] if event["sub_category_id"] else None,
                sub_category_name=event["sub_category_name"] if event["sub_category_name"] else None,
                sub_category_color=sub_category_color,
                description=description,
                app_description=event.get("app_description") or None,
                title_analysis=event.get("title_analysis") or None,
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
    
    def update_event_category(self, event_id: str, category_id: str, sub_category_id: Optional[str] = None) -> bool:
        """
        更新事件的分类信息
        
        Args:
            event_id: 事件ID
            category_id: 主分类ID
            sub_category_id: 子分类ID（可选）
        
        Returns:
            bool: 是否更新成功
        """
        return self.data_provider.update_event_category(event_id, category_id, sub_category_id)
    
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
    
    def get_timeline_overview(
        self, 
        date: str, 
        start_hour: float, 
        end_hour: float
    ) -> dict:
        """
        获取指定时间范围的 Overview 数据
        
        Args:
            date: 日期 (YYYY-MM-DD) - 必填
            start_hour: 开始小时 - 必填
            end_hour: 结束小时 - 必填
            
        Returns:
            dict: TimelineOverviewResponse 格式数据
        """
        from collections import defaultdict
        
        # 1. 从 data_provider 获取数据
        events = self.data_provider.get_events_by_time_range(date, start_hour, end_hour)
        
        # 2. 使用 color_manager 获取颜色
        main_colors = color_manager.get_all_main_colors()
        sub_colors = color_manager.get_all_sub_colors()
        
        # 3. 构建根级别数据 (Category)
        root_data = self._build_overview_data(
            events=events,
            group_field="category_id",
            name_field="category_name",
            color_map=main_colors,
            title=f"{self._format_hour(start_hour)} - {self._format_hour(end_hour)}",
            sub_title="Activity breakdown for selected time range",
            start_hour=start_hour,
            end_hour=end_hour,
            include_blank=True  # 只在根级别添加空白
        )
        
        # 4. 构建 details (Sub-category)
        root_data["details"] = {}
        
        # 按主分类分组
        category_events = defaultdict(list)
        for event in events:
            if event["category_id"]:
                category_events[event["category_id"]].append(event)
        
        for cat_id, cat_events in category_events.items():
            cat_name = cat_events[0]["category_name"] if cat_events else cat_id
            cat_color = main_colors.get(cat_id, "#9CA3AF")
            
            cat_data = self._build_overview_data(
                events=cat_events,
                group_field="sub_category_id",
                name_field="sub_category_name",
                color_map=sub_colors,
                title=f"{cat_name} Details",
                sub_title=f"Breakdown of {cat_name}",
                start_hour=start_hour,
                end_hour=end_hour,
                include_blank=False  # 子级别不添加空白
            )
            
            # 5. 构建 Level 3 (App) - 在每个子分类下添加应用级别
            cat_data["details"] = {}
            
            # 按子分类分组
            sub_cat_events = defaultdict(list)
            for event in cat_events:
                sub_id = event.get("sub_category_id")
                if sub_id:
                    sub_cat_events[sub_id].append(event)
            
            for sub_id, sub_events in sub_cat_events.items():
                sub_name = sub_events[0].get("sub_category_name", sub_id) if sub_events else sub_id
                sub_color = sub_colors.get(sub_id, cat_color)
                
                # 构建 App 级别数据
                app_data = self._build_app_level_data(
                    events=sub_events,
                    title=f"{sub_name} Apps",
                    sub_title=f"Top applications in {sub_name}",
                    base_color=sub_color,
                    start_hour=start_hour,
                    end_hour=end_hour
                )
                cat_data["details"][sub_id] = app_data
            
            root_data["details"][cat_id] = cat_data
        
        return root_data
    
    def _build_overview_data(
        self,
        events: list,
        group_field: str,
        name_field: str,
        color_map: dict,
        title: str,
        sub_title: str,
        start_hour: float,
        end_hour: float,
        include_blank: bool = False  # 是否添加空白类别
    ) -> dict:
        """构建 Overview 数据结构"""
        from collections import defaultdict
        
        # 按分组聚合时长
        group_duration = defaultdict(int)
        group_names = {}
        
        for event in events:
            group_id = event.get(group_field)
            if not group_id:
                continue
            group_duration[group_id] += event.get("duration", 0)
            group_names[group_id] = event.get(name_field, group_id)
        
        total_seconds = sum(group_duration.values())
        total_minutes = total_seconds // 60
        
        # 构建饼图数据
        pie_data = []
        bar_keys = []
        
        for group_id, duration in sorted(group_duration.items(), key=lambda x: x[1], reverse=True):
            name = group_names.get(group_id, group_id)
            color = color_map.get(group_id, "#9CA3AF")
            
            pie_data.append({
                "key": group_id,
                "name": name,
                "value": duration // 60,  # 转换为分钟
                "color": color
            })
            bar_keys.append({
                "key": name,  # 使用名称作为 key
                "label": name,
                "color": color
            })
        
        # 只在根级别添加空白时间
        if include_blank:
            total_range_minutes = int((end_hour - start_hour) * 60)
            blank_minutes = total_range_minutes - int(total_minutes)
            if blank_minutes > 0:
                pie_data.append({
                    "key": "blank",
                    "name": "空白",
                    "value": blank_minutes,
                    "color": "#eeeeee"
                })
                bar_keys.append({
                    "key": "空白",
                    "label": "空白",
                    "color": "#eeeeee"
                })
        
        # 构建 6 刻度柱状图数据
        bar_data = self._build_fixed_interval_bar_data(
            events, group_field, start_hour, end_hour, group_names
        )
        
        return {
            "title": title,
            "subTitle": sub_title,
            "totalTrackedMinutes": int(total_minutes),
            "pieData": pie_data,
            "barKeys": bar_keys,
            "barData": bar_data,
            "details": None
        }
    
    def _build_fixed_interval_bar_data(
        self,
        events: list,
        group_field: str,
        start_hour: float,
        end_hour: float,
        group_names: dict  # 新增参数：ID 到名称的映射
    ) -> list:
        """
        构建固定 6 刻度的柱状图数据
        
        Args:
            events: 事件列表
            group_field: 分组字段
            start_hour: 开始小时
            end_hour: 结束小时
            
        Returns:
            list: 6 个时间刻度的柱状图数据
        """
        from collections import defaultdict
        from datetime import datetime
        
        # 计算每个刻度的时长（分钟）
        total_minutes = (end_hour - start_hour) * 60
        interval_minutes = total_minutes / 6
        
        # 初始化 6 个时间槽
        time_slots = []
        for i in range(6):
            slot_start_min = start_hour * 60 + i * interval_minutes
            slot_hour = int(slot_start_min // 60)
            slot_min = int(slot_start_min % 60)
            time_range = f"{slot_hour:02d}:{slot_min:02d}"
            time_slots.append({
                "timeRange": time_range,
                "start_min": slot_start_min,
                "end_min": slot_start_min + interval_minutes
            })
        
        # 计算每个时间槽的分类时长
        for slot in time_slots:
            slot_start = slot["start_min"]
            slot_end = slot["end_min"]
            
            category_duration = defaultdict(int)
            
            for event in events:
                # 解析事件时间
                event_start = self._parse_time_to_minutes(event["start_time"])
                event_end = self._parse_time_to_minutes(event["end_time"])
                
                # 计算重叠
                overlap_start = max(event_start, slot_start)
                overlap_end = min(event_end, slot_end)
                
                if overlap_start < overlap_end:
                    overlap_minutes = overlap_end - overlap_start
                    group_id = event.get(group_field)
                    if group_id:
                        category_duration[group_id] += overlap_minutes
            
            # 添加分类数据（使用名称而非 ID）
            total_tracked = 0
            for group_id, minutes in category_duration.items():
                group_name = group_names.get(group_id, group_id)
                slot[group_name] = int(minutes)
                total_tracked += minutes
            
            # 计算空白时间
            blank_minutes = interval_minutes - total_tracked
            if blank_minutes > 0:
                slot["空白"] = int(blank_minutes)
            
            # 清理内部字段
            del slot["start_min"]
            del slot["end_min"]
        
        return time_slots
    
    def _parse_time_to_minutes(self, time_str: str) -> float:
        """将时间字符串解析为当天的分钟数"""
        try:
            dt = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
            return dt.hour * 60 + dt.minute + dt.second / 60
        except Exception:
            return 0.0
    
    def _format_hour(self, hour: float) -> str:
        """将小时浮点数格式化为 HH:MM"""
        h = int(hour)
        m = int((hour % 1) * 60)
        return f"{h:02d}:{m:02d}"
    
    def _build_app_level_data(
        self,
        events: list,
        title: str,
        sub_title: str,
        base_color: str,
        start_hour: float,
        end_hour: float
    ) -> dict:
        """
        构建应用级别数据（Top 5 + Other）
        
        Args:
            events: 事件列表
            title: 标题
            sub_title: 副标题
            base_color: 基础颜色（用于生成渐变色）
            start_hour: 开始小时
            end_hour: 结束小时
        """
        from collections import defaultdict
        
        # 按应用分组统计时长
        app_duration = defaultdict(int)
        for event in events:
            app = event.get("app", "Unknown")
            app_duration[app] += event.get("duration", 0)
        
        # 排序并取 Top 5
        sorted_apps = sorted(app_duration.items(), key=lambda x: x[1], reverse=True)
        top_5 = sorted_apps[:5]
        other_apps = sorted_apps[5:]
        
        # 计算 Other 总时长
        other_seconds = sum(d for _, d in other_apps)
        
        # 生成颜色
        num_colors = len(top_5) + (1 if other_seconds > 0 else 0)
        colors = self._generate_color_variants(base_color, num_colors)
        
        pie_data = []
        bar_keys = []
        total_seconds = sum(app_duration.values())
        total_minutes = total_seconds // 60
        
        # 处理 Top 5
        for i, (app_name, seconds) in enumerate(top_5):
            color = colors[i] if i < len(colors) else base_color
            pie_data.append({
                "key": app_name,
                "name": app_name,
                "value": seconds // 60,
                "color": color
            })
            bar_keys.append({
                "key": app_name,
                "label": app_name,
                "color": color
            })
        
        # 处理 Other
        if other_seconds > 0:
            other_color = colors[-1] if colors else "#9CA3AF"
            pie_data.append({
                "key": "Other",
                "name": "Other Apps",
                "value": other_seconds // 60,
                "color": other_color
            })
            bar_keys.append({
                "key": "Other",
                "label": "Other",
                "color": other_color
            })
        
        # App 级别不添加空白（空白只在根级别显示）
        
        return {
            "title": title,
            "subTitle": sub_title,
            "totalTrackedMinutes": int(total_minutes),
            "pieData": pie_data,
            "barKeys": bar_keys,
            "barData": [],  # App 级别暂不需要 barData
            "details": None  # 叶子节点无 details
        }
    
    def _generate_color_variants(self, base_color: str, count: int) -> list:
        """
        基于基础颜色生成渐变色
        """
        if count <= 0:
            return []
        if count == 1:
            return [base_color]
        
        # 简单的亮度变化
        variants = []
        for i in range(count):
            # 将 hex 转换为 RGB
            hex_color = base_color.lstrip('#')
            r = int(hex_color[0:2], 16)
            g = int(hex_color[2:4], 16)
            b = int(hex_color[4:6], 16)
            
            # 调整亮度 (0.7 到 1.0)
            factor = 0.7 + (0.3 * i / (count - 1)) if count > 1 else 1.0
            r = min(255, int(r * factor + (255 - r) * (1 - factor) * 0.5))
            g = min(255, int(g * factor + (255 - g) * (1 - factor) * 0.5))
            b = min(255, int(b * factor + (255 - b) * (1 - factor) * 0.5))
            
            variants.append(f"#{r:02x}{g:02x}{b:02x}")
        
        return variants
