"""
数据处理服务
负责 ActivityWatch 数据的完整处理流程
"""

import logging
import pandas as pd
from typing import Dict, Tuple, Optional
from datetime import datetime, timedelta
import pytz

from lifewatch.server.providers.statistical_data_providers import server_lw_data_provider
from lifewatch.processors.data_clean import clean_activitywatch_data
from lifewatch.llm.llm_classify.classify.main_classify import LLMClassify
from lifewatch.llm.llm_classify.classify.mock_data import mock_goals
from lifewatch.llm.llm_classify.schemas import classifyState
from lifewatch import config

# 配置日志
logger = logging.getLogger(__name__)


class DataProcessingService:
    """
    数据处理服务
    
    封装从 ActivityWatch 获取数据到保存到数据库的完整流程
    提供优化的分类结果合并和批量处理功能
    """
    
    def __init__(self):
        """
        初始化数据处理服务
        
        使用全局单例数据提供者
        """
        self.server_lw_data_provider = server_lw_data_provider
        self._category_mappings_cache = None  # 缓存分类映射
        
    def process_activitywatch_data(
        self,
        auto_classify: bool = True
    ) -> Dict:
        """
        增量同步处理 ActivityWatch 数据
        
        从数据库最新的 end_time 开始获取到现在的数据
        
        Args:
            auto_classify: 是否自动分类新应用
            
        Returns:
            Dict: 处理结果统计
                - total_events: 总事件数
                - filtered_events: 过滤后事件数
                - apps_to_classify: 待分类应用数
                - classified_apps: 已分类应用数
                - saved_events: 保存的事件数
                - sync_mode: 同步模式（始终为 'incremental'）
                - time_range: 同步的时间范围
        """
        try:
            # 获取增量同步的时间范围
            sync_mode = 'incremental'
            start_time, end_time = self._get_incremental_time_range()
            time_range = f"{start_time.strftime('%Y-%m-%d %H:%M:%S')} ~ {end_time.strftime('%Y-%m-%d %H:%M:%S')}"
            
            # 1-2. 获取 ActivityWatch 数据并清洗
            logger.info("步骤 1-2/6: 获取 ActivityWatch 数据并清洗...")
            app_purpose_category_df = self.server_lw_data_provider.load_app_purpose_category()  # 获取已缓存的分类结果
            filtered_data, classify_state = clean_activitywatch_data(
                start_time=start_time,
                end_time=end_time, 
                app_purpose_category_df=app_purpose_category_df
            )
            total_events = len(filtered_data) + (len(classify_state.log_items) if classify_state.log_items else 0)
            filtered_events = len(filtered_data)
            apps_to_classify = len(classify_state.log_items) if classify_state.log_items else 0
            logger.info(f"  ✓ 获取并过滤后保留 {filtered_events} 条事件")
            if not filtered_data.empty:
                logger.info(f"  {filtered_data[['app','duration','start_time','end_time']]}")
            logger.info(f"  ✓ 发现 {apps_to_classify} 条待分类日志项")
            
            classified_apps = 0
            
            # 3. LLM 分类（如果需要）
            if auto_classify and apps_to_classify > 0:
                logger.info(f"步骤 3/6: LLM 分类 {apps_to_classify} 条日志项...")
                classified_app_df = self._classify_apps(classify_state, filtered_events)
                
                # 4. 保存分类结果
                logger.info("步骤 4/6: 保存分类结果...")
                if classified_app_df is not None and not classified_app_df.empty:
                    self.server_lw_data_provider.save_app_purpose_category(classified_app_df)
                    classified_apps = len(classified_app_df)
                    logger.info(f"  ✓ 保存了 {classified_apps} 个应用的分类")
                    
                    # 5. 合并分类结果到事件数据
                    logger.info("步骤 5/6: 合并分类结果...")
                    filtered_data = self._merge_classification_results(
                        filtered_data, 
                        classified_app_df
                    )
                else:
                    logger.warning("  ⚠ 分类结果为空，跳过保存和合并")
            else:
                logger.info("步骤 3-5/6: 跳过分类（auto_classify=False 或无待分类应用）")
            
            # 6. 映射 category_id 和 sub_category_id
            logger.info("步骤 6/6: 映射分类 ID...")
            filtered_data = self._map_category_ids(filtered_data)
            
            # 7. 保存行为日志
            logger.info("保存行为日志到数据库...")
            self.server_lw_data_provider.save_user_app_behavior_log(filtered_data)
            saved_events = len(filtered_data)
            logger.info(f"  ✓ 保存了 {saved_events} 条行为日志")
            
            # 统计结果
            result = {
                "total_events": total_events,
                "filtered_events": filtered_events,
                "apps_to_classify": apps_to_classify,
                "classified_apps": classified_apps,
                "saved_events": saved_events,
                "unclassified_events": len(filtered_data[filtered_data['category_id'].isna()]),
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
    
    def process_activitywatch_data_by_time_range(
        self,
        start_time: datetime,
        end_time: datetime,
        auto_classify: bool
    ) -> Dict:
        """
        按时间范围处理 ActivityWatch 数据
        
        Args:
            start_time: 开始时间 (datetime对象)
            end_time: 结束时间 (datetime对象)
            auto_classify: 是否自动分类新应用
            
        Returns:
            Dict: 处理结果统计
        """
        try:
            time_range = f"{start_time.strftime('%Y-%m-%d %H:%M:%S')} ~ {end_time.strftime('%Y-%m-%d %H:%M:%S')}"
            logger.info(f"开始按时间范围同步数据: {time_range}")
            
            # 1-2. 获取 ActivityWatch 数据并清洗
            logger.info("步骤 1-2/6: 获取 ActivityWatch 数据并清洗...")
            app_purpose_category_df = self.server_lw_data_provider.load_app_purpose_category()
            filtered_data, classify_state = clean_activitywatch_data(
                start_time=start_time,
                end_time=end_time,
                # app_purpose_category_df=app_purpose_category_df
                app_purpose_category_df=None
            )
            total_events = len(filtered_data) + (len(classify_state.log_items) if classify_state.log_items else 0)
            filtered_events = len(filtered_data)
            apps_to_classify = len(classify_state.log_items) if classify_state.log_items else 0
            logger.info(f"  ✓ 获取并过滤后保留 {filtered_events} 条事件")
            logger.info(f"  ✓ 发现 {apps_to_classify} 条待分类日志项")
            
            classified_apps = 0
            
            # 3. LLM 分类（如果需要）
            if auto_classify and apps_to_classify > 0:
                logger.info(f"步骤 3/6: LLM 分类 {apps_to_classify} 条日志项...")
                classified_app_df = self._classify_apps(classify_state, filtered_events)
                
                # 4. 保存分类结果
                logger.info("步骤 4/6: 保存分类结果...")
                if classified_app_df is not None and not classified_app_df.empty:
                    self.server_lw_data_provider.save_app_purpose_category(classified_app_df)
                    classified_apps = len(classified_app_df)
                    logger.info(f"  ✓ 保存了 {classified_apps} 个应用的分类")
                    
                    # 5. 合并分类结果到事件数据
                    logger.info("步骤 5/6: 合并分类结果...")
                    filtered_data = self._merge_classification_results(
                        filtered_data, 
                        classified_app_df
                    )
                else:
                    logger.warning("  ⚠ 分类结果为空，跳过保存和合并")
            else:
                logger.info("步骤 3-5/6: 跳过分类（auto_classify=False 或无待分类应用）")
            
            # 6. 映射 category_id 和 sub_category_id
            logger.info("步骤 6/6: 映射分类 ID...")
            filtered_data = self._map_category_ids(filtered_data)
            
            # 7. 保存行为日志
            logger.info("保存行为日志到数据库...")
            self.server_lw_data_provider.save_user_app_behavior_log(filtered_data)
            saved_events = len(filtered_data)
            logger.info(f"  ✓ 保存了 {saved_events} 条行为日志")
            
            # 统计结果
            result = {
                "total_events": total_events,
                "filtered_events": filtered_events,
                "apps_to_classify": apps_to_classify,
                "classified_apps": classified_apps,
                "saved_events": saved_events,
                "unclassified_events": len(filtered_data[filtered_data['category_id'].isna()]),
                "sync_mode": "time_range",
                "time_range": time_range
            }
            
            logger.info("=" * 60)
            logger.info("数据处理完成！")
            logger.info(f"  - 同步模式: time_range")
            logger.info(f"  - 时间范围: {time_range}")
            logger.info(f"  - 总事件数: {total_events}")
            logger.info(f"  - 有效事件数: {filtered_events}")
            logger.info(f"  - 新分类应用数: {classified_apps}")
            logger.info(f"  - 保存事件数: {saved_events}")
            logger.info(f"  - 未分类事件数: {result['unclassified_events']}")
            logger.info("=" * 60)
            
            return result
            
        except Exception as e:
            logger.error(f"时间范围数据处理失败: {e}", exc_info=True)
            raise
    

    def _get_incremental_time_range(self):
        """
        获取增量同步的时间范围
        
        从数据库最新的 end_time 开始获取到现在
        如果数据库为空，则获取最近24小时的数据（首次同步）

        Returns:
            start_time: 开始时间
            end_time: 结束时间
        """
        local_tz = pytz.timezone(config.LOCAL_TIMEZONE)
        latest_end_time = self.server_lw_data_provider.get_latest_end_time()
        
        if latest_end_time:
            # 增量同步：从数据库最新的 end_time 开始获取到现在
            latest_dt = datetime.strptime(latest_end_time, '%Y-%m-%d %H:%M:%S')
            start_time = local_tz.localize(latest_dt)
            end_time = datetime.now(local_tz)
            time_diff = end_time - start_time
            hours_diff = time_diff.total_seconds() / 3600
            logger.info(f"开始增量同步 ActivityWatch 数据")
            logger.info(f"  开始时间: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info(f"  结束时间: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info(f"  时间跨度: {hours_diff:.2f} 小时")
        else:
            # 数据库为空，首次同步：获取最近24小时
            start_time = datetime.now(local_tz) - timedelta(hours=24)
            end_time = datetime.now(local_tz)
            logger.info("数据库为空，执行首次同步（24小时）")

        return start_time, end_time

    def _classify_apps(self, classify_state: classifyState, filtered_events: int) -> pd.DataFrame:
        """
        使用 LLM 分类应用
        
        Args:
            classify_state: 待分类数据的 classifyState 对象
            filtered_events: 过滤后的事件数量，用于统计
            
        Returns:
            pd.DataFrame: 包含分类结果的 DataFrame
        """
        # 获取 category 和 sub_category
        category = self.server_lw_data_provider.load_categories()
        sub_category = self.server_lw_data_provider.load_sub_categories()
        
        # 构建分类名称到ID的映射
        category_name_to_id = {}
        sub_category_name_to_id = {}
        if category is not None and not category.empty:
            category_name_to_id = category.set_index('name')['id'].to_dict()
        if sub_category is not None and not sub_category.empty:
            sub_category_name_to_id = sub_category.set_index('name')['id'].to_dict()
        
        # 构建分类树结构：{主分类名: [子分类名列表]}
        # 只包含启用的分类（state == 1）
        category_tree = {}
        for _, cat in category.iterrows():
            # 过滤被禁用的主分类
            if cat.get('state', 1) == 0:
                logger.info(f"  跳过禁用的主分类: {cat['name']}")
                continue
            
            cat_id = cat['id']
            cat_name = cat['name']
            # 找到属于该主分类的所有启用的子分类
            sub_mask = sub_category['category_id'] == cat_id
            if 'state' in sub_category.columns:
                sub_mask = sub_mask & (sub_category['state'].fillna(1) == 1)
            enabled_subs = sub_category[sub_mask]['name'].tolist()
            category_tree[cat_name] = enabled_subs
        
        logger.info(f"  构建分类树（仅启用分类）: {category_tree}")
        
        # 严格检查：如果分类树为空，则无法进行分类
        if not category_tree:
            logger.error("所有分类均被禁用，无法进行 LLM 分类！请至少启用一个主分类。")
            return pd.DataFrame()
        
        # 获取分类模式
        classify_mode = getattr(config, 'CLASSIFY_MODE', 'classify_graph')
        logger.info(f"  使用分类模式: {classify_mode}")
        
        # 初始化 LLMClassify 分类器
        classifier = LLMClassify(
            classify_mode=classify_mode,
            goal=mock_goals,
            category_tree=category_tree
        )
        
        # 执行分类
        logger.info(f"  调用 LLM 分类器...")
        result = classifier.classify(classify_state)
        logger.info(f"  ✓ 分类完成")
        
        # 处理分类结果
        if result is None or not result.get('result_items'):
            logger.warning("  ⚠ 分类结果为空")
            return pd.DataFrame()
        
        result_items = result['result_items']
        logger.info(f"  ✓ 获取到 {len(result_items)} 条分类结果")
        
        # 保存 token 使用数据（使用 filtered_events 作为 result_items_count）
        self._save_tokens_usage(result, filtered_events)
        
        # 转换为 DataFrame 格式（适配 app_purpose_category 表结构）
        # 按 app 分组处理：单用途应用只保存一条，多用途应用保存所有 title
        classified_records = []
        app_groups = {}  # {app: [items]}
        
        # 先按 app 分组
        for item in result_items:
            if item.app not in app_groups:
                app_groups[item.app] = []
            app_groups[item.app].append(item)
        
        # 处理每个 app 组
        for app, items in app_groups.items():
            is_multipurpose = classify_state.app_registry.get(app, None)
            is_multipurpose_flag = 1 if (is_multipurpose and is_multipurpose.is_multipurpose) else 0
            
            if is_multipurpose_flag == 0:
                # 单用途应用：只保存第一条记录（代表性记录）
                item = items[0]
                # 获取分类ID
                cat_id = category_name_to_id.get(item.category) if item.category else None
                sub_cat_id = sub_category_name_to_id.get(item.sub_category) if item.sub_category else None
                
                classified_records.append({
                    'app': item.app,
                    'title': item.title,
                    'is_multipurpose_app': is_multipurpose_flag,
                    'app_description': is_multipurpose.description if is_multipurpose else None,
                    'title_analysis': item.title_analysis,
                    'category_id': cat_id,
                    'sub_category_id': sub_cat_id,
                    'category': item.category,  # 保留用于调试
                    'sub_category': item.sub_category,  # 保留用于调试
                })
                if len(items) > 1:
                    logger.info(f"    单用途应用 '{app}' 有 {len(items)} 条记录，只保存第一条")
            else:
                # 多用途应用：保存所有不同 title 的记录
                for item in items:
                    # 获取分类ID
                    cat_id = category_name_to_id.get(item.category) if item.category else None
                    sub_cat_id = sub_category_name_to_id.get(item.sub_category) if item.sub_category else None
                    
                    classified_records.append({
                        'app': item.app,
                        'title': item.title,
                        'is_multipurpose_app': is_multipurpose_flag,
                        'app_description': is_multipurpose.description if is_multipurpose else None,
                        'title_analysis': item.title_analysis,
                        'category_id': cat_id,
                        'sub_category_id': sub_cat_id,
                        'category': item.category,  # 保留用于调试
                        'sub_category': item.sub_category,  # 保留用于调试
                    })
        
        logger.info(f"  ✓ 处理后保留 {len(classified_records)} 条分类记录（原始 {len(result_items)} 条）")
        classified_app_df = pd.DataFrame(classified_records)
        
        # 验证分类结果
        logger.info(f"  验证分类结果...")
        classified_app_df = self._validate_classification_results(classified_app_df, category_tree)
        logger.info(f"  ✓ 验证完成")
        
        return classified_app_df
    
    def _validate_classification_results(self, df: pd.DataFrame, category_tree: dict) -> pd.DataFrame:
        """
        验证分类结果是否符合层级规则
        
        规则（按优先级）：
        1. A是主分类，B必须是A下的子分类（层级匹配）
        2. 若能确定A但无法确定B，则A正常分类，B返回null（合法）
        3. 若无法确定A，则A和B都返回null（合法）
        4. 若B不属于A的子分类，视为错误，A和B都返回null
        
        Args:
            df: 包含分类结果的DataFrame
            category_tree: 分类树结构 {"主分类": ["子分类列表"]}
            
        Returns:
            pd.DataFrame: 验证并修正后的DataFrame
        """
        invalid_count = 0
        
        for idx in df.index:
            cat = df.at[idx, 'category']
            sub_cat = df.at[idx, 'sub_category']
            
            # 规则3: 两者都为None是合法的
            if pd.isna(cat) and pd.isna(sub_cat):
                continue
            
            # 规则4: A为None但B有值，不合法 -> 修正为都为None
            if pd.isna(cat) and not pd.isna(sub_cat):
                logger.warning(f"    ⚠ 索引 {idx}: 主分类为None但子分类为'{sub_cat}'，修正为都为None")
                df.at[idx, 'sub_category'] = None
                invalid_count += 1
                continue
            
            # 规则2: A有值但B为None是合法的（A必须在分类树中）
            if not pd.isna(cat) and pd.isna(sub_cat):
                if cat not in category_tree:
                    logger.warning(f"    ⚠ 索引 {idx}: 主分类'{cat}'不在分类树中，修正为None")
                    df.at[idx, 'category'] = None
                    invalid_count += 1
                continue
            
            # 规则1: A和B都有值，需要验证层级关系
            if not pd.isna(cat) and not pd.isna(sub_cat):
                # 检查主分类是否存在
                if cat not in category_tree:
                    logger.warning(f"    ⚠ 索引 {idx}: 主分类'{cat}'不在分类树中，修正为都为None")
                    df.at[idx, 'category'] = None
                    df.at[idx, 'sub_category'] = None
                    invalid_count += 1
                    continue
                
                # 检查子分类是否属于该主分类
                if sub_cat not in category_tree[cat]:
                    logger.warning(
                        f"    ⚠ 索引 {idx}: 子分类'{sub_cat}'不属于主分类'{cat}'，"
                        f"期望子分类为{category_tree[cat]}，修正为都为None"
                    )
                    df.at[idx, 'category'] = None
                    df.at[idx, 'sub_category'] = None
                    invalid_count += 1
                    continue
        
        if invalid_count > 0:
            logger.info(f"    修正了 {invalid_count} 条不符合规则的分类结果")
        else:
            logger.info(f"    所有分类结果均符合规则")
        
        return df
    
    def _merge_classification_results(
        self,
        filtered_data: pd.DataFrame,
        classified_app_df: pd.DataFrame
    ) -> pd.DataFrame:
        """
        优化的分类结果合并逻辑（使用 pandas merge 替代 iterrows）
        
        使用 category_id 和 sub_category_id 进行合并（而非名称）
        
        Args:
            filtered_data: 过滤后的事件数据
            classified_app_df: 分类结果数据
            
        Returns:
            pd.DataFrame: 合并后的数据
        """
        logger.info("  使用向量化操作合并分类结果...")
        
        # 确保列存在
        if 'category_id' not in filtered_data.columns:
            filtered_data['category_id'] = None
        if 'sub_category_id' not in filtered_data.columns:
            filtered_data['sub_category_id'] = None
        
        # 分离单用途和多用途应用
        single_purpose = classified_app_df[classified_app_df['is_multipurpose_app'] == 0].copy()
        multi_purpose = classified_app_df[classified_app_df['is_multipurpose_app'] == 1].copy()
        
        # 处理单用途应用：只按 app 匹配
        if not single_purpose.empty:
            # 转换为小写以匹配
            single_purpose['app_lower'] = single_purpose['app'].str.lower()
            filtered_data['app_lower'] = filtered_data['app'].str.lower()
            
            # 只保留需要的列，避免列名冲突
            single_merge = single_purpose[['app_lower', 'category_id', 'sub_category_id']].rename(
                columns={'category_id': 'category_id_single', 'sub_category_id': 'sub_category_id_single'}
            )
            
            # 合并单用途应用的分类
            filtered_data = filtered_data.merge(
                single_merge,
                on='app_lower',
                how='left'
            )
            
            # 只更新单用途应用的分类（is_multipurpose_app == 0）
            mask_single = (filtered_data['is_multipurpose_app'] == 0) & (filtered_data['category_id_single'].notna())
            filtered_data.loc[mask_single, 'category_id'] = filtered_data.loc[mask_single, 'category_id_single']
            filtered_data.loc[mask_single, 'sub_category_id'] = filtered_data.loc[mask_single, 'sub_category_id_single']
            
            # 删除临时列
            filtered_data = filtered_data.drop(columns=['category_id_single', 'sub_category_id_single'])
            
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
            multi_merge = multi_purpose[['app_lower', 'title_lower', 'category_id', 'sub_category_id']].rename(
                columns={'category_id': 'category_id_multi', 'sub_category_id': 'sub_category_id_multi'}
            )
            
            # 合并多用途应用的分类
            filtered_data = filtered_data.merge(
                multi_merge,
                on=['app_lower', 'title_lower'],
                how='left'
            )
            
            # 只更新多用途应用的分类（is_multipurpose_app == 1）
            mask_multi = (filtered_data['is_multipurpose_app'] == 1) & (filtered_data['category_id_multi'].notna())
            filtered_data.loc[mask_multi, 'category_id'] = filtered_data.loc[mask_multi, 'category_id_multi']
            filtered_data.loc[mask_multi, 'sub_category_id'] = filtered_data.loc[mask_multi, 'sub_category_id_multi']
            
            # 删除临时列
            filtered_data = filtered_data.drop(columns=['category_id_multi', 'sub_category_id_multi'])
            
            logger.info(f"    ✓ 合并了 {mask_multi.sum()} 个多用途应用的分类")
        
        # 清理临时列
        if 'app_lower' in filtered_data.columns:
            filtered_data = filtered_data.drop(columns=['app_lower'])
        if 'title_lower' in filtered_data.columns:
            filtered_data = filtered_data.drop(columns=['title_lower'])
        
        # 统计
        total_classified = filtered_data['category_id'].notna().sum()
        logger.info(f"  ✓ 总共合并了 {total_classified} 条记录的分类")
        
        return filtered_data
    
    def _map_category_ids(self, filtered_data: pd.DataFrame) -> pd.DataFrame:
        """
        批量映射 category_id 和 sub_category_id，并删除冗余的名称列
        
        Args:
            filtered_data: 包含 category 和 sub_category 的数据
            
        Returns:
            pd.DataFrame: 只包含 category_id 和 sub_category_id 的数据（名称列已删除）
        """
        # 获取或使用缓存的映射字典
        if self._category_mappings_cache is None:
            category = self.server_lw_data_provider.load_categories()
            sub_category = self.server_lw_data_provider.load_sub_categories()
            
            # 处理分类为空的情况
            category_dict = {}
            if category is not None and not category.empty:
                category_dict = category.set_index('name')['id'].to_dict()
                
            sub_category_dict = {}
            if sub_category is not None and not sub_category.empty:
                sub_category_dict = sub_category.set_index('name')['id'].to_dict()
            
            self._category_mappings_cache = {
                'category_id_dict': category_dict,
                'sub_category_id_dict': sub_category_dict
            }
            logger.info("  ✓ 创建分类映射字典缓存")
        
        # 批量映射
        if 'category' in filtered_data.columns:
            filtered_data['category_id'] = filtered_data['category'].map(
                self._category_mappings_cache['category_id_dict']
            )
        if 'sub_category' in filtered_data.columns:
            filtered_data['sub_category_id'] = filtered_data['sub_category'].map(
                self._category_mappings_cache['sub_category_id_dict']
            )
        
        # 统计映射结果
        mapped_count = filtered_data['category_id'].notna().sum() if 'category_id' in filtered_data.columns else 0
        logger.info(f"  ✓ 映射了 {mapped_count} 条记录的分类 ID")
        
        return filtered_data
    
    def _save_tokens_usage(self, result: dict, result_items_count: int):
        """
        保存 token 使用数据到数据库
        
        Args:
            result: LLM 分类结果字典，包含 tokens_usage 信息
            result_items_count: 分类结果项目数
        """
        try:
            # 从 result 中提取 tokens_usage 字典
            tokens_usage = result.get('tokens_usage', {})
            input_tokens = tokens_usage.get('input_tokens', 0)
            output_tokens = tokens_usage.get('output_tokens', 0)
            total_tokens = tokens_usage.get('total_tokens', 0)
            search_count = tokens_usage.get('search_count', 0)
            
            # 创建 DataFrame
            tokens_usage_data = pd.DataFrame([{
                'input_tokens': input_tokens,
                'output_tokens': output_tokens,
                'total_tokens': total_tokens,
                'search_count': search_count,
                'result_items_count': result_items_count,
                'mode': 'classification'
            }])
            
            # 保存到数据库
            self.server_lw_data_provider.save_tokens_usage(tokens_usage_data)
            logger.info(f"  ✓ 保存 token 使用数据: input={input_tokens}, output={output_tokens}, total={total_tokens}")
            
        except Exception as e:
            logger.error(f"保存 token 使用数据失败: {e}")
            # 不抛出异常，避免影响主流程
    
    def clear_cache(self):
        """清除缓存的映射字典"""
        self._category_mappings_cache = None
        logger.info("已清除分类映射缓存")


if __name__ == "__main__":
    data_processing_service = DataProcessingService()
    start_time = datetime.now() - timedelta(hours=1)
    end_time = datetime.now()
    data_processing_service.process_activitywatch_data_by_time_range(auto_classify=True, start_time=start_time, end_time=end_time)