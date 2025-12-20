# """
# 首页统一数据模型 - Pydantic V2 兼容版本
# 整合活动总结、仪表盘数据和时间概览的统一响应
# """

# from pydantic import BaseModel, Field
# from .dashboard import DashboardResponse
# from .activity_summary_schemas import ActivitySummaryResponse
# from .dashboard_schemas import TimeOverviewResponse


# class HomepageResponse(BaseModel):
#     """
#     首页统一API响应
    
#     整合以下三个部分的数据：
#     - activity_summary: 活动总结条形图数据
#     - dashboard: 仪表盘数据（top应用、top标题、分类统计）
#     - time_overview: 时间概览图表数据
#     """
#     activity_summary: ActivitySummaryResponse = Field(..., description="活动总结数据")
#     dashboard: DashboardResponse = Field(..., description="仪表盘数据")
#     time_overview: TimeOverviewResponse = Field(..., description="时间概览数据")
