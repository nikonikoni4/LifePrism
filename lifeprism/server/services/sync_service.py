"""
数据同步服务
负责从 ActivityWatch 同步数据并分类
"""

import time
from datetime import datetime
from typing import Dict
from lifeprism.server.services.data_processing_service import DataProcessingService

import asyncio
import json
from datetime import datetime, timedelta

from lifeprism.llm.function import screenshot_analysis,screenshot_behavior_summary
from lifeprism.config import settings
from lifeprism.server.schemas.timeline_schemas import BehaviorAnalysisItem
from lifeprism.repository import todo_repository,QueryOptions

async def screen_behavior_anlysis(start_time:str,end_time:str) ->list[BehaviorAnalysisItem]:
    """
    分析规定时间内的屏幕截图,返回分析结果列表
    args :
        start_time : 开始时间，支持格式：
                    - "YYYY-MM-DD HH:MM:SS" (标准格式)
                    - "YYYY-MM-DDTHH:MM:SS" (ISO 8601格式)
        end_time : 结束时间，格式同上
    return

    """
    # 0. 时间格式转换：将 ISO 8601 格式转换为标准格式
    # 替换 'T' 为空格，确保统一格式
    start_time = start_time.replace('T', ' ')
    end_time = end_time.replace('T', ' ')

    # 1. 计算开始时间
    screenshot_retention_days = settings.get("screenshot_retention_days", 3)
    requested_start_time = datetime.fromisoformat(start_time)
    earliest_available_time = datetime.now().replace(microsecond=0) - timedelta(days=screenshot_retention_days)
    start_time = max(requested_start_time, earliest_available_time).replace(microsecond=0).strftime("%Y-%m-%d %H:%M:%S")
    
    #2.  查询todolist
    todolist,_ = todo_repository.query_todos(
        QueryOptions()
        .with_date_range(start_time[:10], end_time[:10])
        .with_order('date', desc=False)
    )
    if todolist:
        # 提取每个 todo 的 content 字段并格式化
        todo_contents = [f"- {todo.get('content', '')}" for todo in todolist]
        todolist = f"""
        ## 计划列表
        {chr(10).join(todo_contents)}
        """
    # 2. 分析屏幕截图
    analysis_results_list = await screenshot_analysis(start_time, end_time,todolist)
    
    # 3. 对分析结果进行摘要分析
    summary_results = await screenshot_behavior_summary(analysis_results_list,todolist)

    return summary_results

class SyncService:
    """
    数据同步服务
    
    整合现有业务逻辑，实现从 ActivityWatch 同步数据的完整流程
    """
    
    def __init__(self):
        self.data_processor = DataProcessingService()
    
    async def incremental_sync(
        self,
        auto_classify: bool = True
    ) -> Dict:
        """
        增量同步 ActivityWatch 数据 /  lifeprism windows_events（从数据库最新时间同步到现在）

        Args:
            auto_classify: 是否自动分类新应用

        Returns:
            Dict: 同步结果
        """
        start_time = time.time()


        # 使用 DataProcessingService 处理增量同步
        result = await self.data_processor.process_activitywatch_data(
            auto_classify=auto_classify
        )

        if settings.monitor_type == "lifeprism" and settings.get("screenshot_monitor", False):
            # 查询 behavior_analysis 表中最后一条记录的 end_time
            from lifeprism.repository import behavior_analysis_repository, QueryOptions

            # 获取最后一条记录（按 end_time 降序）
            options = QueryOptions().with_order('end_time', desc=True).with_limit(1)
            last_records, _ = behavior_analysis_repository.query_behaviors(options)

            if last_records:
                # 使用最后一条记录的 end_time 作为起始时间
                analysis_start_time = last_records[0]['end_time']
            else:
                # 如果表为空，使用当前时间往前推 1 天
                analysis_start_time = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")

            # 使用当前时间作为结束时间
            analysis_end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # 后台执行截图分析，不阻塞 sync 响应
            asyncio.create_task(screen_behavior_anlysis(analysis_start_time, analysis_end_time))
        duration = time.time() - start_time
        return {
            "status": "success",
            "synced_events": result["saved_events"],
            "new_apps_classified": result["classified_apps"],
            "duration": round(duration, 2),
            "message": f"成功同步数据（增量模式）",
            "details": {
                "sync_mode": result["sync_mode"],
                "time_range": result["time_range"],
                "total_events": result["total_events"],
                "filtered_events": result["filtered_events"],
                "apps_to_classify": result["apps_to_classify"],
                "unclassified_events": result["unclassified_events"]
            }
        }
        
        
    
    async def sync_by_time_range(
        self,
        start_time: str,
        end_time: str,
        auto_classify: bool = True
    ) -> Dict:
        """
        按时间范围同步 ActivityWatch 数据
        
        Args:
            start_time: 开始时间，格式: YYYY-MM-DD HH:MM:SS
            end_time: 结束时间，格式: YYYY-MM-DD HH:MM:SS
            auto_classify: 是否自动分类新应用
            
        Returns:
            Dict: 同步结果
        """
        sync_start = time.time()
        
        
        # 解析时间字符串
        start_dt = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
        end_dt = datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S")
        
        # 使用 DataProcessingService 处理数据
        result = await self.data_processor.process_activitywatch_data_by_time_range(
            start_time=start_dt,
            end_time=end_dt,
            auto_classify=auto_classify
        )
        if settings.monitor_type == "lifeprism" and settings.get("screenshot_monitor", False):
            # time_range 格式: "2026-04-19 11:00:00 ~ 2026-04-19 11:15:00"
            time_parts = result["time_range"].split(" ~ ")
            # 后台执行截图分析，不阻塞 sync 响应
            asyncio.create_task(screen_behavior_anlysis(time_parts[0], time_parts[1]))
        duration = time.time() - sync_start
        
        return {
            "status": "success",
            "synced_events": result["saved_events"],
            "new_apps_classified": result["classified_apps"],
            "duration": round(duration, 2),
            "message": f"成功同步时间范围数据",
            "details": {
                "sync_mode": "time_range",
                "time_range": result["time_range"],
                "total_events": result["total_events"],
                "filtered_events": result["filtered_events"],
                "apps_to_classify": result["apps_to_classify"],
                "unclassified_events": result["unclassified_events"]
            }
        }
         
if __name__ == "__main__":
    from lifeprism.llm.agent.loop import agent_loop
    import asyncio
    
    async def main():
        loop_task = asyncio.create_task(agent_loop.loop())
        # logger.info("[STARTUP] AgentLoop started") # logger is not imported in this file
        response = await screen_behavior_anlysis("2026-04-19 11:00:00","2026-04-19 11:15:00")
        print(response)
        loop_task.cancel() # Cancel the loop task when done to exit cleanly
        
    asyncio.run(main())