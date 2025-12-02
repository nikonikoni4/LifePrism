"""
数据同步服务
负责从 ActivityWatch 同步数据并分类
"""

import time
from datetime import datetime
from typing import Dict
from lifewatch.storage.lifewatch_data_manager import LifeWatchDataManager
from lifewatch.server.services.data_processing_service import DataProcessingService


class SyncService:
    """
    数据同步服务
    
    整合现有业务逻辑，实现从 ActivityWatch 同步数据的完整流程
    """
    
    def __init__(self):
        self.db = LifeWatchDataManager()
        self.data_processor = DataProcessingService()
    
    def sync_from_activitywatch(
        self,
        hours: int = 24,
        auto_classify: bool = True
    ) -> Dict:
        """
        从 ActivityWatch 同步数据
        
        Args:
            hours: 同步最近N小时的数据
            auto_classify: 是否自动分类新应用
            
        Returns:
            Dict: 同步结果
        """
        # 使用真实同步逻辑（基于 DataProcessingService）
        return self._real_sync(hours, auto_classify)
        
        # 如需使用 Mock 数据进行测试，取消下面的注释
        # return self._mock_sync(hours, auto_classify)
    
    def _mock_sync(self, hours: int, auto_classify: bool) -> Dict:
        """返回 Mock 同步结果"""
        # 模拟同步耗时
        time.sleep(0.5)
        
        return {
            "status": "success",
            "synced_events": 156,
            "new_apps_classified": 5 if auto_classify else 0,
            "duration": 0.5,
            "message": f"成功同步最近 {hours} 小时的数据（Mock）"
        }
    
    def _real_sync(self, hours: int, auto_classify: bool) -> Dict:
        """
        真实的数据同步逻辑
        
        使用 DataProcessingService 处理完整的数据流程
        """
        start_time = time.time()
        
        try:
            # 使用 DataProcessingService 处理数据
            result = self.data_processor.process_activitywatch_data(
                hours=hours,
                auto_classify=auto_classify
            )
            
            duration = time.time() - start_time
            
            return {
                "status": "success",
                "synced_events": result["saved_events"],
                "new_apps_classified": result["classified_apps"],
                "duration": round(duration, 2),
                "message": f"成功同步最近 {hours} 小时的数据",
                "details": {
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
