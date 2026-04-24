from datetime import datetime, timedelta

from lifeprism.llm.function import screenshot_analysis,behavior_summary
from lifeprism.config import settings
from lifeprism.server.schemas.timeline_schemas import BehaviorAnalysisItem

def _format_analysis_time(value: datetime) -> str:
    return value.replace(microsecond=0).strftime("%Y-%m-%d %H:%M:%S")


def screen_behavior_anlysis(start_time:str,end_time:str) ->list[BehaviorAnalysisItem]:
    """
    分析规定时间内的屏幕截图
    args : 
        start_time : 开始时间 YYYY-MM-DD HH-MM-SS
        end_time : 结束时间
    return 
    """
    # 1. 计算开始时间
    screenshot_retention_days = settings.get("screenshot_retention_days", 3)
    requested_start_time = datetime.fromisoformat(start_time)
    earliest_available_time = datetime.now().replace(microsecond=0) - timedelta(days=screenshot_retention_days)
    start_time = max(requested_start_time, earliest_available_time).replace(microsecond=0).strftime("%Y-%m-%d %H:%M:%S")
    



