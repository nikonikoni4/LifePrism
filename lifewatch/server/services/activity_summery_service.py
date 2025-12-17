import datetime
from lifewatch.server.providers.statistical_data_providers import ServerLWDataProvider
from lifewatch.server.schemas.activity_summary_schemas import DailyActivitiesResponse,ActivitySummaryResponse
from lifewatch.server.services.category_service import CategoryService
from typing import List, Optional

class ActivitySummaryService:
    def __init__(self):
        self.statistical_data_provider = ServerLWDataProvider()
        self.category_service = CategoryService()
        
    def get_activity_summary_data(
        self, 
        date: str,
        history_days: int,
        future_days: int,
        category_id: Optional[str] = None,
        sub_category_id: Optional[str] = None
    ):
        """获取活动总结数据，支持按分类筛选"""
        # 计算开始时间和结束时间
        center_date = datetime.datetime.strptime(date, "%Y-%m-%d")
        start_date = (center_date - datetime.timedelta(days=history_days)).strftime("%Y-%m-%d")
        end_date = (center_date + datetime.timedelta(days=future_days)).strftime("%Y-%m-%d")
        
        # 获取查询范围内的所有日期
        date_range = []
        current_date = center_date - datetime.timedelta(days=history_days)
        end_date_obj = center_date + datetime.timedelta(days=future_days)
        
        while current_date <= end_date_obj:
            date_range.append(current_date.strftime("%Y-%m-%d"))
            current_date += datetime.timedelta(days=1)
        
        # 查询数据库中的实际数据（带分类筛选）
        daily_activities = self.statistical_data_provider.get_daily_active_time(
            start_date, end_date, category_id, sub_category_id
        )
        
        # 创建日期到活动数据的映射
        activity_map = {item["date"]: item["active_time_percentage"] for item in daily_activities}
        
        # 获取分类颜色（如果指定了分类筛选）
        filter_color = None
        if category_id:
            category = self.category_service.get_category_by_id(category_id)
            if category:
                filter_color = category.get("color")
        
        # 构建完整的数据数组，缺失的日期补全为0
        activity_summary_data: List[DailyActivitiesResponse] = []
        for date_str in date_range:
            active_percentage = activity_map.get(date_str, 0)  # 没有数据的日期默认为0
            daily_activities_response = DailyActivitiesResponse(
                date=date_str,
                active_time_percentage=active_percentage,
                color=filter_color  # 使用分类颜色
            )
            activity_summary_data.append(daily_activities_response)
            
        # 获取今日活动时长
        today_active_time = self.statistical_data_provider.get_active_time(date)
        # 将秒转换为小时和分钟
        hours = int(today_active_time // 3600)
        minutes = int((today_active_time % 3600) // 60)
        return ActivitySummaryResponse(
            dailyActivities=activity_summary_data,
            today_active_time=f"{hours}h {minutes}m"
        )

if __name__ == "__main__":
    as_service = ActivitySummaryService()
    print(as_service.get_activity_summary_data("2025-12-4", 7, 7))

