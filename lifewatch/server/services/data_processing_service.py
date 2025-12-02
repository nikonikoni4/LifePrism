"""
数据处理服务
负责 ActivityWatch 数据的完整处理流程
"""

import logging
import pandas as pd
from typing import Dict, Tuple, Optional
from datetime import datetime, timedelta
import pytz

from lifewatch.storage.lifewatch_data_manager import LifeWatchDataManager
from lifewatch.data.get_activitywatch_data import get_window_events
from lifewatch.data.data_clean import clean_activitywatch_data
from lifewatch.llm.cloud_classifier import QwenAPIClassifier
from lifewatch import config

# 配置日志
logger = logging.getLogger(__name__)


class DataProcessingService:
    """
    数据处理服务
    
    封装从 ActivityWatch 获取数据到保存到数据库的完整流程
    提供优化的分类结果合并和批量处理功能
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """
        初始化数据处理服务
        
        Args:
            db_path: 数据库路径，默认使用 config.DB_PATH
        """
        self.db_manager = LifeWatchDataManager(db_path=db_path or config.DB_PATH)
        self._category_mappings_cache = None  # 缓存分类映射
        
    def process_activitywatch_data(
        self,
        hours: int = 24,
        auto_classify: bool = True,
        use_incremental_sync: bool = False
    ) -> Dict:
        """
        处理 ActivityWatch 数据的完整流程
        
        Args:
            hours: 获取最近N小时的数据（当 use_incremental_sync=False 时使用）
            auto_classify: 是否自动分类新应用
            use_incremental_sync: 是否使用增量同步
                - True: 从数据库最新的 end_time 开始获取到现在的数据
                - False: 获取最近 hours 小时的数据（默认）
            
        Returns:
            Dict: 处理结果统计
                - total_events: 总事件数
                - filtered_events: 过滤后事件数
                - apps_to_classify: 待分类应用数
                - classified_apps: 已分类应用数
                - saved_events: 保存的事件数
                - sync_mode: 同步模式（'incremental' 或 'full'）
                - time_range: 同步的时间范围
        """
        try:
            # 确定同步模式和时间范围
            sync_mode = 'incremental' if use_incremental_sync else 'full'
            
            if use_incremental_sync:
                # 增量同步：从数据库最新的 end_time 开始
                latest_end_time = self.db_manager.get_latest_end_time()
                
                if latest_end_time:
                    # 计算从最新时间到现在的小时数
                    latest_dt = datetime.strptime(latest_end_time, '%Y-%m-%d %H:%M:%S')
                    # 假设数据库时间是本地时区
                    local_tz = pytz.timezone(config.LOCAL_TIMEZONE)
                    latest_dt = local_tz.localize(latest_dt)
                    now_dt = datetime.now(local_tz)
                    
                    time_diff = now_dt - latest_dt
                    hours_since_last = int(time_diff.total_seconds() / 3600) + 1  # 向上取整，确保覆盖
                    
                    logger.info(f"开始增量同步 ActivityWatch 数据")
                    logger.info(f"  上次同步时间: {latest_end_time}")
                    logger.info(f"  时间跨度: {hours_since_last} 小时")
                    
                    hours = hours_since_last
                    time_range = f"{latest_end_time} ~ 现在"
                else:
                    # 数据库为空，使用默认的 24 小时
                    logger.info("数据库为空，执行首次全量同步（24小时）")
                    hours = 24
                    sync_mode = 'full'
                    time_range = f"最近 {hours} 小时"
            else:
                # 全量同步：获取最近 N 小时
                logger.info(f"开始全量同步 ActivityWatch 数据 (最近 {hours} 小时)")
                time_range = f"最近 {hours} 小时"
            
            # 1. 获取 ActivityWatch 数据
            logger.info("步骤 1/6: 获取 ActivityWatch 数据...")
            aw_data = get_window_events(hours=hours)
            total_events = len(aw_data)
            logger.info(f"  ✓ 获取到 {total_events} 条原始事件")
            
            # 2. 数据清洗
            logger.info("步骤 2/6: 数据清洗...")
            app_purpose_category_df = self.db_manager.load_app_purpose_category()
            filtered_data, app_to_classify_df, app_to_classify_set = clean_activitywatch_data(
                aw_data, 
                app_purpose_category_df
            )
            filtered_events = len(filtered_data)
            apps_to_classify = len(app_to_classify_df)
            logger.info(f"  ✓ 过滤后保留 {filtered_events} 条事件")
            logger.info(f"  ✓ 发现 {apps_to_classify} 个待分类应用")
            
            classified_apps = 0
            
            # 3. LLM 分类（如果需要）
            if auto_classify and apps_to_classify > 0:
                logger.info(f"步骤 3/6: LLM 分类 {apps_to_classify} 个应用...")
                classified_app_df = self._classify_apps(app_to_classify_df)
                
                # 4. 保存分类结果
                logger.info("步骤 4/6: 保存分类结果...")
                self.db_manager.save_app_purpose_category(classified_app_df)
                classified_apps = len(classified_app_df)
                logger.info(f"  ✓ 保存了 {classified_apps} 个应用的分类")
                
                # 5. 合并分类结果到事件数据
                logger.info("步骤 5/6: 合并分类结果...")
                filtered_data = self._merge_classification_results(
                    filtered_data, 
                    classified_app_df
                )
            else:
                logger.info("步骤 3-5/6: 跳过分类（auto_classify=False 或无待分类应用）")
            
            # 6. 映射 category_id 和 sub_category_id
            logger.info("步骤 6/6: 映射分类 ID...")
            filtered_data = self._map_category_ids(filtered_data)
            
            # 7. 保存行为日志
            logger.info("保存行为日志到数据库...")
            self.db_manager.save_user_app_behavior_log(filtered_data)
            saved_events = len(filtered_data)
            logger.info(f"  ✓ 保存了 {saved_events} 条行为日志")
            
            # 统计结果
            result = {
                "total_events": total_events,
                "filtered_events": filtered_events,
                "apps_to_classify": apps_to_classify,
                "classified_apps": classified_apps,
                "saved_events": saved_events,
                "unclassified_events": len(filtered_data[filtered_data['category'].isna()]),
                "sync_mode": sync_mode,
                "time_range": time_range
            }
            
            logger.info("=" * 60)
            logger.info("数据处理完成！")
            logger.info(f"  - 同步模式: {sync_mode}")
            logger.info(f"  - 时间范围: {time_range}")
            logger.info(f"  - 总事件数: {total_events}")
            logger.info(f"  - 有效事件数: {filtered_events}")
            logger.info(f"  - 新分类应用数: {classified_apps}")
            logger.info(f"  - 保存事件数: {saved_events}")
            logger.info(f"  - 未分类事件数: {result['unclassified_events']}")
            logger.info("=" * 60)
            
            return result
            
        except Exception as e:
            logger.error(f"数据处理失败: {e}", exc_info=True)
            raise
    
    def _classify_apps(self, app_to_classify_df: pd.DataFrame) -> pd.DataFrame:
        """
        使用 LLM 分类应用
        
        Args:
            app_to_classify_df: 待分类应用 DataFrame
            
        Returns:
            pd.DataFrame: 包含分类结果的 DataFrame
        """
        # 获取 category 和 sub_category
        category = self.db_manager.load_categories()
        sub_category = self.db_manager.load_sub_categories()
        
        # 初始化分类器
        classifier = QwenAPIClassifier(
            api_key=config.MODEL_KEY[config.SELECT_MODEL]["api_key"],
            base_url=config.MODEL_KEY[config.SELECT_MODEL]["base_url"],
            model=config.SELECT_MODEL,
            category=", ".join(category['name'].tolist()),
            sub_category=", ".join(sub_category['name'].tolist())
        )
        
        # 执行分类
        logger.info(f"  调用 LLM 分类器...")
        classified_app_df = classifier.classify(app_to_classify_df)
        logger.info(f"  ✓ 分类完成")
        
        return classified_app_df
    
    def _merge_classification_results(
        self,
        filtered_data: pd.DataFrame,
        classified_app_df: pd.DataFrame
    ) -> pd.DataFrame:
        """
        优化的分类结果合并逻辑（使用 pandas merge 替代 iterrows）
        
        Args:
            filtered_data: 过滤后的事件数据
            classified_app_df: 分类结果数据
            
        Returns:
            pd.DataFrame: 合并后的数据
        """
        logger.info("  使用向量化操作合并分类结果...")
        
        # 确保列存在
        if 'category' not in filtered_data.columns:
            filtered_data['category'] = None
        if 'sub_category' not in filtered_data.columns:
            filtered_data['sub_category'] = None
        
        # 分离单用途和多用途应用
        single_purpose = classified_app_df[classified_app_df['is_multipurpose_app'] == 0].copy()
        multi_purpose = classified_app_df[classified_app_df['is_multipurpose_app'] == 1].copy()
        
        # 处理单用途应用：只按 app 匹配
        if not single_purpose.empty:
            # 转换为小写以匹配
            single_purpose['app_lower'] = single_purpose['app'].str.lower()
            filtered_data['app_lower'] = filtered_data['app'].str.lower()
            
            # 只保留需要的列，避免列名冲突
            single_merge = single_purpose[['app_lower', 'category', 'sub_category']].rename(
                columns={'category': 'category_single', 'sub_category': 'sub_category_single'}
            )
            
            # 合并单用途应用的分类
            filtered_data = filtered_data.merge(
                single_merge,
                on='app_lower',
                how='left'
            )
            
            # 只更新单用途应用的分类（is_multipurpose_app == 0）
            mask_single = (filtered_data['is_multipurpose_app'] == 0) & (filtered_data['category_single'].notna())
            filtered_data.loc[mask_single, 'category'] = filtered_data.loc[mask_single, 'category_single']
            filtered_data.loc[mask_single, 'sub_category'] = filtered_data.loc[mask_single, 'sub_category_single']
            
            # 删除临时列
            filtered_data = filtered_data.drop(columns=['category_single', 'sub_category_single'])
            
            logger.info(f"    ✓ 合并了 {mask_single.sum()} 个单用途应用的分类")
        
        # 处理多用途应用：按 (app, title) 匹配
        if not multi_purpose.empty:
            # 转换为小写以匹配
            multi_purpose['app_lower'] = multi_purpose['app'].str.lower()
            multi_purpose['title_lower'] = multi_purpose['title'].str.lower()
            
            if 'app_lower' not in filtered_data.columns:
                filtered_data['app_lower'] = filtered_data['app'].str.lower()
            filtered_data['title_lower'] = filtered_data['title'].str.lower()
            
            # 只保留需要的列
            multi_merge = multi_purpose[['app_lower', 'title_lower', 'category', 'sub_category']].rename(
                columns={'category': 'category_multi', 'sub_category': 'sub_category_multi'}
            )
            
            # 合并多用途应用的分类
            filtered_data = filtered_data.merge(
                multi_merge,
                on=['app_lower', 'title_lower'],
                how='left'
            )
            
            # 只更新多用途应用的分类（is_multipurpose_app == 1）
            mask_multi = (filtered_data['is_multipurpose_app'] == 1) & (filtered_data['category_multi'].notna())
            filtered_data.loc[mask_multi, 'category'] = filtered_data.loc[mask_multi, 'category_multi']
            filtered_data.loc[mask_multi, 'sub_category'] = filtered_data.loc[mask_multi, 'sub_category_multi']
            
            # 删除临时列
            filtered_data = filtered_data.drop(columns=['category_multi', 'sub_category_multi'])
            
            logger.info(f"    ✓ 合并了 {mask_multi.sum()} 个多用途应用的分类")
        
        # 清理临时列
        if 'app_lower' in filtered_data.columns:
            filtered_data = filtered_data.drop(columns=['app_lower'])
        if 'title_lower' in filtered_data.columns:
            filtered_data = filtered_data.drop(columns=['title_lower'])
        
        # 统计
        total_classified = filtered_data['category'].notna().sum()
        logger.info(f"  ✓ 总共合并了 {total_classified} 条记录的分类")
        
        return filtered_data
    
    def _map_category_ids(self, filtered_data: pd.DataFrame) -> pd.DataFrame:
        """
        批量映射 category_id 和 sub_category_id
        
        Args:
            filtered_data: 包含 category 和 sub_category 的数据
            
        Returns:
            pd.DataFrame: 添加了 category_id 和 sub_category_id 的数据
        """
        # 获取或使用缓存的映射字典
        if self._category_mappings_cache is None:
            category = self.db_manager.load_categories()
            sub_category = self.db_manager.load_sub_categories()
            
            self._category_mappings_cache = {
                'category_id_dict': category.set_index('name')['id'].to_dict(),
                'sub_category_id_dict': sub_category.set_index('name')['id'].to_dict()
            }
            logger.info("  ✓ 创建分类映射字典缓存")
        
        # 批量映射
        filtered_data['category_id'] = filtered_data['category'].map(
            self._category_mappings_cache['category_id_dict']
        )
        filtered_data['sub_category_id'] = filtered_data['sub_category'].map(
            self._category_mappings_cache['sub_category_id_dict']
        )
        
        # 统计映射结果
        mapped_count = filtered_data['category_id'].notna().sum()
        logger.info(f"  ✓ 映射了 {mapped_count} 条记录的分类 ID")
        
        return filtered_data
    
    def clear_cache(self):
        """清除缓存的映射字典"""
        self._category_mappings_cache = None
        logger.info("已清除分类映射缓存")
