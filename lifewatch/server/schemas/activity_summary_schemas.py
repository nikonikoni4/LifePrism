# """
# 活动总结相关数据模型 - Pydantic V2 兼容版本
# """

# from pydantic import BaseModel, Field
# from typing import List, Optional
# from datetime import date

# class DailyActivitiesResponse(BaseModel):
#     """每日活动数据项"""
#     date: str = Field(..., description="日期（YYYY-MM-DD 格式）")
#     active_time_percentage: int = Field(..., description="活动时长占比（%）", alias="activeTimePercentage")
#     color: Optional[str] = Field(None, description="分类颜色（十六进制格式）")
    
#     class Config:
#         populate_by_name = True

# class ActivitySummaryResponse(BaseModel):
#     """活动总结API响应"""
#     today_active_time: str = Field(..., description="今日活动时长", alias="todayActiveTime")
#     daily_activities: List[DailyActivitiesResponse] = Field(..., description="每日活动数据数组", alias="dailyActivities")
#     class Config:
#         populate_by_name = True