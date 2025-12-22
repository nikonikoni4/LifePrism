"""
数据同步服务
负责从 ActivityWatch 同步数据并分类
"""

import time
from datetime import datetime
from typing import Dict
from lifewatch.server.services.data_processing_service import DataProcessingService


class SyncService:
    """
    数据同步服务
    
    整合现有业务逻辑，实现从 ActivityWatch 同步数据的完整流程
    """
    
    def __init__(self):
        self.data_processor = DataProcessingService()
    
    def sync_from_activitywatch(
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
        
        try:
            # 使用 DataProcessingService 处理增量同步
            result = self.data_processor.process_activitywatch_data(
                auto_classify=auto_classify
            )
            
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
            
        except Exception as e:
            duration = time.time() - start_time
            return {
                "status": "failed",
                "synced_events": 0,
                "new_apps_classified": 0,
                "duration": round(duration, 2),
                "message": f"同步失败: {str(e)}"
            }
    
    def sync_by_time_range(
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
        
        try:
            # 解析时间字符串
            start_dt = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
            end_dt = datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S")
            
            # 使用 DataProcessingService 处理数据
            result = self.data_processor.process_activitywatch_data_by_time_range(
                start_time=start_dt,
                end_time=end_dt,
                auto_classify=auto_classify
            )
            
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
            
        except Exception as e:
            duration = time.time() - sync_start
            return {
                "status": "failed",
                "synced_events": 0,
                "new_apps_classified": 0,
                "duration": round(duration, 2),
                "message": f"时间范围同步失败: {str(e)}"
            }
