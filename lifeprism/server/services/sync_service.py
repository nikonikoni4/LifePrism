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

from lifeprism.llm.function import screenshot_analysis,behavior_summary
from lifeprism.config import settings
from lifeprism.server.schemas.timeline_schemas import BehaviorAnalysisItem
from lifeprism.storage import todo_store,QueryOptions

async def screen_behavior_anlysis(start_time:str,end_time:str) ->list[BehaviorAnalysisItem]:
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
    
    # 2. 获取时间范围内的toddolist

    todolist = await todo_store.get_todolist(QueryOptions(
        start_time=start_time,
        end_time=end_time,
    ))

    # 2. 分析屏幕截图
    analysis_results_list = await screenshot_analysis(start_time, end_time,todolist)
    
    # 3. 对相邻的结果进行合并
    merged_results = []
    for i in range(len(analysis_results_list)):
        if i == 0 or analysis_results_list[i]['start_time'] != analysis_results_list[i-1]['end_time']:
            merged_results.append(analysis_results_list[i])
        else:
            merged_results[-1]['screenshot_count'] += analysis_results_list[i]['screenshot_count']
            merged_results[-1]['behavior'] += analysis_results_list[i]['behavior']

    # 4. 摘要分析
    todolist_text = "\n".join([f"- {todo.content}" for todo in todolist]) if todolist else ""
    
    async def get_summary_and_title(merged_item: dict) -> dict:
        summary_result = await behavior_summary(merged_item['behavior'], todolist_text)
        result = json.loads(summary_result)
        merged_item['behavior_summary'] = result.get('behavior_summary', '')
        merged_item['title'] = result.get('title', '')
        merged_item['behaviors'] = merged_item.pop('behavior')
        return merged_item
    
    merged_results = await asyncio.gather(*[get_summary_and_title(item) for item in merged_results])
    
    return [BehaviorAnalysisItem(**item) for item in merged_results]


class SyncService:
    """
    数据同步服务
    
    整合现有业务逻辑，实现从 ActivityWatch 同步数据的完整流程
    """
    
    def __init__(self):
        self.data_processor = DataProcessingService()
    
    async def sync_from_activitywatch(
        self,
        auto_classify: bool = True
    ) -> Dict:
        """
        增量同步 ActivityWatch 数据（从数据库最新时间同步到现在）
        
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
        
        
        await screen_behavior_anlysis(result["time_range"]["start"],result["time_range"]["end"])
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
        await screen_behavior_anlysis(result["time_range"]["start"],result["time_range"]["end"])
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
         
