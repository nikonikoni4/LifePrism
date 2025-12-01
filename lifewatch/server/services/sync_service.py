"""
数据同步服务
负责从 ActivityWatch 同步数据并分类
"""

import time
from datetime import datetime
from typing import Dict
from lifewatch.storage.lifewatch_data_manager import LifeWatchDataManager

# 以下导入仅在真实同步逻辑中使用，暂时注释掉
# from  lifewatch.data.get_activitywatch_data import ActivityWatchTimeRangeAccessor
# from lifewatch.data.data_clean import clean_activitywatch_data
# from lifewatch.crawler.app_description_fetching import AppDescriptionFetcher
# from lifewatch.llm.ollama_client import OllamaClient
# from lifewatch import config


class SyncService:
    """
    数据同步服务
    
    整合现有业务逻辑，实现从 ActivityWatch 同步数据的完整流程
    """
    
    def __init__(self):
        self.db = LifeWatchDataManager()
    
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
        # 第一阶段：返回 Mock 同步结果
        return self._mock_sync(hours, auto_classify)
        
        # 第二阶段：实现真实同步逻辑
        # return self._real_sync(hours, auto_classify)
    
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
        
        基于 mian.py 中的业务流程实现
        
        TODO: 第二阶段实现
        1. 从 ActivityWatch 获取数据
        2. 数据清洗
        3. 查询待分类应用
        4. 抓取应用描述（如果需要）
        5. 调用 LLM 分类（如果 auto_classify=True）
        6. 保存到数据库
        7. 返回同步结果
        """
        start_time = time.time()
        
        try:
            # 1. 获取 ActivityWatch 数据
            aw_accessor = ActivityWatchTimeRangeAccessor(
                base_url=config.AW_URL_CONFIG["base_url"],
                local_tz=config.LOCAL_TIMEZONE
            )
            user_behavior_logs = aw_accessor.get_window_events(hours=hours)
            
            # 2. 读取已有分类
            app_purpose_category_df = self.db.load_app_purpose_category()
            
            # 3. 数据清洗
            filtered_events_df, apps_to_classify_df, apps_to_classify_set = clean_activitywatch_data(
                user_behavior_logs,
                app_purpose_category_df
            )
            
            synced_events = len(filtered_events_df)
            new_apps_classified = 0
            
            # 4. 如果需要分类且有待分类应用
            if auto_classify and len(apps_to_classify_df) > 0:
                # 获取应用描述
                app_description_fetcher = AppDescriptionFetcher("BaiDuBrowerCrawler")
                app_descriptions_dict = app_description_fetcher.fetch_batch_app_descriptions(
                    apps_to_classify_set
                )
                
                # 添加描述到 DataFrame
                apps_to_classify_df['app_description'] = apps_to_classify_df['app'].map(
                    app_descriptions_dict
                )
                
                # LLM 分类
                client = OllamaClient(config.OLLAMA_BASE_URL)
                processed_df = process_and_fill_dataframe(
                    apps_to_classify_df,
                    mock_llm_func=lambda batch: call_ollama_llm_api(
                        batch, client, config.CATEGORY_A, config.CATEGORY_B
                    )
                )
                
                # 保存分类结果
                self.db.save_app_purpose_category(processed_df)
                new_apps_classified = len(processed_df)
                
                # TODO: 将分类结果赋值给 filtered_events_df
                # （参考 mian.py 中的逻辑）
            
            # 5. 保存行为日志
            self.db.save_user_app_behavior_log(filtered_events_df)
            
            duration = time.time() - start_time
            
            return {
                "status": "success",
                "synced_events": synced_events,
                "new_apps_classified": new_apps_classified,
                "duration": round(duration, 2),
                "message": f"成功同步最近 {hours} 小时的数据"
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
