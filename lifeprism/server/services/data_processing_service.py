"""
数据处理服务
负责 ActivityWatch 数据的完整处理流程
"""

import logging
from datetime import datetime, timedelta, timezone

import pandas as pd
import pytz

from lifeprism.config import get_user_timezone, settings
from lifeprism.llm.classify.main_classify import LLMClassify
from lifeprism.llm.schemas import classifyState
from lifeprism.processors.data_clean import clean_activitywatch_data
from lifeprism.repository import goal_repository, tokens_usage_repository
from lifeprism.server.providers import server_lw_data_provider
from lifeprism.utils import LWBaseError, get_logger
from lifeprism.utils.time_utils import get_local_today

# 配置日志
logger = get_logger(__name__, logging.DEBUG)


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
        self._goal_name_to_id_cache = None  # 缓存 goal 名称到 ID 的映射

    async def process_activitywatch_data(self, auto_classify: bool = True) -> dict:
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
            sync_mode = "incremental"
            start_time, end_time = self._get_incremental_time_range()
            time_range = f"{start_time.isoformat()} ~ {end_time.isoformat()}"

            # 1-2. 获取 ActivityWatch 数据并清洗
            logger.info("步骤 1-2/6: 获取 ActivityWatch 数据并清洗...")
            category_map_cache_df = (
                self.server_lw_data_provider.load_category_map_cache_V2()
            )  # 获取已缓存的分类结果
            filtered_data, classify_state = clean_activitywatch_data(
                start_time=start_time,
                end_time=end_time,
                category_map_cache_df=category_map_cache_df,
            )
            total_events = len(filtered_data) + (
                len(classify_state.log_items) if classify_state.log_items else 0
            )
            filtered_events = len(filtered_data)
            apps_to_classify = len(classify_state.log_items) if classify_state.log_items else 0
            logger.info("  [OK] 获取并过滤后保留 %s 条事件", filtered_events)
            if not filtered_data.empty:
                logger.debug("  %s", filtered_data[["app", "duration", "start_time", "end_time"]])
            logger.info("  [OK] 发现 %s 条待分类日志项", apps_to_classify)

            classified_apps = 0

            # 3. LLM 分类（如果需要）
            if auto_classify and apps_to_classify > 0:
                logger.info("步骤 3/6: LLM 分类 %s 条日志项...", apps_to_classify)
                classified_app_df = await self._classify_apps(classify_state, filtered_events)

                # 4. 保存分类结果
                logger.info("步骤 4/6: 保存分类结果...")
                if classified_app_df is not None and not classified_app_df.empty:
                    self.server_lw_data_provider.save_category_map_cache_V2(classified_app_df)
                    classified_apps = len(classified_app_df)
                    logger.info("  [OK] 保存了 %s 个应用的分类", classified_apps)

                    # 5. 合并分类结果到事件数据
                    logger.info("步骤 5/6: 合并分类结果...")
                    filtered_data = self._merge_classification_results(
                        filtered_data, classified_app_df
                    )
                else:
                    logger.warning("  [!] 分类结果为空，跳过保存和合并")
            else:
                logger.info("步骤 3-5/6: 跳过分类（auto_classify=False 或无待分类应用）")

            # 6. 映射 category_id 和 sub_category_id
            logger.info("步骤 6/6: 映射分类 ID...")
            filtered_data = self._map_category_ids(filtered_data)

            # 7. 保存行为日志
            logger.info("保存行为日志到数据库...")
            self.server_lw_data_provider.save_user_app_behavior_log(filtered_data)
            saved_events = len(filtered_data)
            logger.info("  [OK] 保存了 %s 条行为日志", saved_events)

            # 统计结果
            result = {
                "total_events": total_events,
                "filtered_events": filtered_events,
                "apps_to_classify": apps_to_classify,
                "classified_apps": classified_apps,
                "saved_events": saved_events,
                "unclassified_events": len(filtered_data[filtered_data["category_id"].isna()]),
                "sync_mode": sync_mode,
                "time_range": time_range,
            }

            logger.info("=" * 60)
            logger.info("数据处理完成！")
            logger.info("  - 同步模式: %s", sync_mode)
            logger.info("  - 时间范围: %s", time_range)
            logger.info("  - 总事件数: %s", total_events)
            logger.info("  - 有效事件数: %s", filtered_events)
            logger.info("  - 新分类应用数: %s", classified_apps)
            logger.info("  - 保存事件数: %s", saved_events)
            logger.info("  - 未分类事件数: %s", result["unclassified_events"])
            logger.info("=" * 60)

            return result

        except LWBaseError:
            raise
        except Exception as e:
            logger.error("数据处理失败: error=%s", e, exc_info=True)
            raise

    async def process_activitywatch_data_by_time_range(
        self, start_time: datetime, end_time: datetime, auto_classify: bool
    ) -> dict:
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
            time_range = f"{start_time.isoformat()} ~ {end_time.isoformat()}"
            logger.info("开始按时间范围同步数据: %s", time_range)

            # 1-2. 获取 ActivityWatch 数据并清洗
            logger.info("步骤 1-2/6: 获取 ActivityWatch 数据并清洗...")
            category_map_cache_df = self.server_lw_data_provider.load_category_map_cache_V2()
            filtered_data, classify_state = clean_activitywatch_data(
                start_time=start_time,
                end_time=end_time,
                category_map_cache_df=category_map_cache_df,
            )
            total_events = len(filtered_data) + (
                len(classify_state.log_items) if classify_state.log_items else 0
            )
            filtered_events = len(filtered_data)
            apps_to_classify = len(classify_state.log_items) if classify_state.log_items else 0
            logger.info("  [OK] 获取并过滤后保留 %s 条事件", filtered_events)
            logger.info("  [OK] 发现 %s 条待分类日志项", apps_to_classify)

            classified_apps = 0

            # 3. LLM 分类（如果需要）
            if auto_classify and apps_to_classify > 0:
                logger.info("步骤 3/6: LLM 分类 %s 条日志项...", apps_to_classify)
                classified_app_df = await self._classify_apps(classify_state, filtered_events)

                # 4. 保存分类结果
                logger.info("步骤 4/6: 保存分类结果...")
                if classified_app_df is not None and not classified_app_df.empty:
                    self.server_lw_data_provider.save_category_map_cache_V2(classified_app_df)
                    classified_apps = len(classified_app_df)
                    logger.info("  [OK] 保存了 %s 个应用的分类", classified_apps)

                    # 5. 合并分类结果到事件数据
                    logger.info("步骤 5/6: 合并分类结果...")
                    filtered_data = self._merge_classification_results(
                        filtered_data, classified_app_df
                    )
                else:
                    logger.warning("  [!] 分类结果为空，跳过保存和合并")
            else:
                logger.info("步骤 3-5/6: 跳过分类（auto_classify=False 或无待分类应用）")

            # 6. 映射 category_id 和 sub_category_id
            logger.info("步骤 6/6: 映射分类 ID...")
            filtered_data = self._map_category_ids(filtered_data)

            # 7. 保存行为日志
            logger.info("保存行为日志到数据库...")
            self.server_lw_data_provider.save_user_app_behavior_log(filtered_data)
            saved_events = len(filtered_data)
            logger.info("  [OK] 保存了 %s 条行为日志", saved_events)

            # 统计结果
            result = {
                "total_events": total_events,
                "filtered_events": filtered_events,
                "apps_to_classify": apps_to_classify,
                "classified_apps": classified_apps,
                "saved_events": saved_events,
                "unclassified_events": len(filtered_data[filtered_data["category_id"].isna()]),
                "sync_mode": "time_range",
                "time_range": time_range,
            }

            logger.info("=" * 60)
            logger.info("数据处理完成！")
            logger.info("  - 同步模式: time_range")
            logger.info("  - 时间范围: %s", time_range)
            logger.info("  - 总事件数: %s", total_events)
            logger.info("  - 有效事件数: %s", filtered_events)
            logger.info("  - 新分类应用数: %s", classified_apps)
            logger.info("  - 保存事件数: %s", saved_events)
            logger.info("  - 未分类事件数: %s", result["unclassified_events"])
            logger.info("=" * 60)

            return result

        except LWBaseError:
            raise
        except Exception as e:
            logger.error("时间范围数据处理失败: error=%s", e, exc_info=True)
            raise

    def _get_incremental_time_range(self):
        """
        获取增量同步的时间范围

        从数据库最新的 end_time 开始获取到现在
        如果数据库为空，则获取最近24小时的数据（首次同步）

        Returns:
            start_time: 开始时间 (UTC aware datetime)
            end_time: 结束时间 (UTC aware datetime)
        """
        latest_end_time = self.server_lw_data_provider.get_latest_end_time()

        if latest_end_time:
            # 增量同步：从数据库最新的 end_time 开始获取到现在
            start_time = self._parse_latest_end_time(latest_end_time)
            end_time = datetime.now(timezone.utc)
            time_diff = end_time - start_time
            hours_diff = time_diff.total_seconds() / 3600
            logger.info("开始增量同步 ActivityWatch 数据")
            logger.info("  开始时间: %s", start_time.isoformat())
            logger.info("  结束时间: %s", end_time.isoformat())
            logger.info("  时间跨度: %.2f 小时", hours_diff)
        else:
            # 数据库为空，首次同步：获取最近24小时
            start_time = datetime.now(timezone.utc) - timedelta(hours=24)
            end_time = datetime.now(timezone.utc)
            logger.info("数据库为空，执行首次同步（24小时）")

        return start_time, end_time

    def _parse_latest_end_time(self, latest_end_time: str) -> datetime:
        """
        解析数据库中最新的 end_time 字符串为 UTC aware datetime

        处理两种格式：
        - 新格式（UTC ISO 8601）：2026-07-12T10:00:00+00:00
        - 旧格式（本地时间）：2026-07-12 10:00:00 或 2026-07-12T10:00:00

        旧格式数据假设为本地时间，转换为 UTC。

        Args:
            latest_end_time: 数据库中的 end_time 字符串

        Returns:
            UTC aware datetime 对象
        """
        try:
            # 尝试解析为新格式（ISO 8601，带时区）
            dt = datetime.fromisoformat(latest_end_time)
            if dt.tzinfo is None:
                # 旧格式（无时区信息），假设为本地时间，转换为 UTC
                local_tz = pytz.timezone(get_user_timezone())
                dt = local_tz.localize(dt)
                dt = dt.astimezone(timezone.utc)
            return dt
        except ValueError:
            # 尝试解析为旧格式 "%Y-%m-%d %H:%M:%S"
            try:
                dt = datetime.strptime(latest_end_time, "%Y-%m-%d %H:%M:%S")
                local_tz = pytz.timezone(get_user_timezone())
                dt = local_tz.localize(dt)
                dt = dt.astimezone(timezone.utc)
                return dt
            except ValueError as e:
                logger.warning("无法解析 end_time: %s, 错误: %s", latest_end_time, e)
                # 解析失败，回退到24小时前
                return datetime.now(timezone.utc) - timedelta(hours=24)

    async def _classify_apps(
        self, classify_state: classifyState, filtered_events: int
    ) -> pd.DataFrame:
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
        # sub_category 使用复合 key (category_name, sub_category_name) -> sub_category_id
        # 避免不同主分类下同名子分类（如"其他"）的 dict key 冲突
        sub_category_composite_to_id = {}
        if category is not None and not category.empty:
            category_name_to_id = category.set_index("name")["id"].to_dict()
            category_id_to_name = category.set_index("id")["name"].to_dict()
        else:
            category_id_to_name = {}
        if sub_category is not None and not sub_category.empty:
            for _, row in sub_category.iterrows():
                parent_cat_name = category_id_to_name.get(row["category_id"], "")
                sub_category_composite_to_id[(parent_cat_name, row["name"])] = row["id"]

        # 构建 goal 名称到 ID 的映射（用于将 LLM 输出的 link_to_goal 名称转换为 ID）
        # 只包含 track_time_automatically=1 且绑定了分类的目标
        if self._goal_name_to_id_cache is None:
            goals = goal_repository.get_active_goals_for_classify()
            self._goal_name_to_id_cache = {g["name"]: g["id"] for g in goals}
            logger.info(
                "  [OK] 创建 goal 名称映射缓存，共 %s 个可自动追踪目标",
                len(self._goal_name_to_id_cache),
            )
            logger.debug("  [DEBUG] goal_name_to_id 映射: %s", self._goal_name_to_id_cache)
        goal_name_to_id = self._goal_name_to_id_cache

        # 构建分类树结构：{主分类名: [子分类名列表]}
        # 只包含启用的分类（state == 1）
        category_tree = {}
        if category is None or category.empty:
            logger.error("主分类数据为空，无法进行 LLM 分类！")
            return pd.DataFrame()
        if sub_category is None:
            sub_category = pd.DataFrame(columns=["category_id", "name", "state"])
        for _, cat in category.iterrows():
            # 过滤被禁用的主分类
            if cat.get("state", 1) == 0:
                logger.debug("  跳过禁用的主分类: %s", cat["name"])
                continue

            cat_id = cat["id"]
            cat_name = cat["name"]
            # 找到属于该主分类的所有启用的子分类
            sub_mask = sub_category["category_id"] == cat_id
            if "state" in sub_category.columns:
                sub_mask = sub_mask & (sub_category["state"].fillna(1) == 1)
            enabled_subs = sub_category[sub_mask]["name"].tolist()
            category_tree[cat_name] = enabled_subs

        logger.info("  构建分类树（仅启用分类）: %s", category_tree)

        # 严格检查：如果分类树为空，则无法进行分类
        if not category_tree:
            logger.error("所有分类均被禁用，无法进行 LLM 分类！请至少启用一个主分类。")
            return pd.DataFrame()

        # 获取分类模式
        classify_mode = settings.classification_mode
        logger.info("  使用分类模式: %s", classify_mode)

        # 构建 goals 列表（用于 LLM 分类时的 goal 关联）
        # 格式: [{goal: 目标名称, category: 主分类名称, sub_category: 子分类名称}, ...]
        from lifeprism.llm.schemas import Goal as LLMGoal

        goals_for_llm = []
        for g in goal_repository.get_active_goals_for_classify():
            # 根据 ID 查找分类名称
            cat_name = None
            sub_cat_name = None
            if g.get("link_to_category_id"):
                cat_row = category[category["id"] == g["link_to_category_id"]]
                if not cat_row.empty:
                    cat_name = cat_row.iloc[0]["name"]
            if g.get("link_to_sub_category_id"):
                sub_row = sub_category[sub_category["id"] == g["link_to_sub_category_id"]]
                if not sub_row.empty:
                    sub_cat_name = sub_row.iloc[0]["name"]

            goals_for_llm.append(
                LLMGoal(goal=g["name"], category=cat_name, sub_category=sub_cat_name)
            )

        logger.info(
            "  [OK] 构建 goals 列表，共 %s 个可自动追踪目标（已过滤被禁用分类和未开启自动追踪的目标）",
            len(goals_for_llm),
        )

        # 初始化 LLMClassify 分类器
        classifier = LLMClassify(
            classify_mode=classify_mode, goal=goals_for_llm, category_tree=category_tree
        )

        # 执行分类
        logger.info("  调用 LLM 分类器...")
        result = await classifier.classify(classify_state)
        logger.info("  [OK] 分类完成")
        logger.debug("  分类结果: %s", result)
        # 处理分类结果
        if result is None or not result.get("result_items"):
            logger.warning("  ! 分类结果为空")
            return pd.DataFrame()

        result_items = result["result_items"]
        logger.info("  [OK] 获取到 %s 条分类结果", len(result_items))

        # 保存 token 使用数据（使用 filtered_events 作为 result_items_count）
        self._save_tokens_usage(result, filtered_events)

        # 转换为 DataFrame 格式（适配 category_map 表结构）
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
                # 获取分类ID（子分类使用复合 key 消歧同名子分类）
                cat_id = category_name_to_id.get(item.category) if item.category else None
                sub_cat_id = (
                    sub_category_composite_to_id.get((item.category, item.sub_category))
                    if item.sub_category
                    else None
                )
                # 将 link_to_goal 名称转换为 ID
                goal_id = goal_name_to_id.get(item.link_to_goal) if item.link_to_goal else None
                if item.link_to_goal:
                    logger.debug(
                        "  [DEBUG] 单用途 '%s': link_to_goal='%s' -> goal_id='%s'",
                        app,
                        item.link_to_goal,
                        goal_id,
                    )

                classified_records.append(
                    {
                        "app": item.app,
                        "title": item.title,
                        "is_multipurpose_app": is_multipurpose_flag,
                        "app_description": is_multipurpose.description if is_multipurpose else None,
                        "title_analysis": item.title_analysis,
                        "category_id": cat_id,
                        "sub_category_id": sub_cat_id,
                        "link_to_goal_id": goal_id,  # 新增: 关联的目标ID
                        "category": item.category,  # 保留用于调试
                        "sub_category": item.sub_category,  # 保留用于调试
                    }
                )
                if len(items) > 1:
                    logger.debug("    单用途应用 '%s' 有 %s 条记录，只保存第一条", app, len(items))
            else:
                # 多用途应用：保存所有不同 title 的记录
                for item in items:
                    # 获取分类ID（子分类使用复合 key 消歧同名子分类）
                    cat_id = category_name_to_id.get(item.category) if item.category else None
                    sub_cat_id = (
                        sub_category_composite_to_id.get((item.category, item.sub_category))
                        if item.sub_category
                        else None
                    )
                    # 将 link_to_goal 名称转换为 ID
                    goal_id = goal_name_to_id.get(item.link_to_goal) if item.link_to_goal else None
                    if item.link_to_goal:
                        logger.debug(
                            "  [DEBUG] 多用途 '%s' title='%s': link_to_goal='%s' -> goal_id='%s'",
                            app,
                            item.title[:30],
                            item.link_to_goal,
                            goal_id,
                        )

                    classified_records.append(
                        {
                            "app": item.app,
                            "title": item.title,
                            "is_multipurpose_app": is_multipurpose_flag,
                            "app_description": is_multipurpose.description
                            if is_multipurpose
                            else None,
                            "title_analysis": item.title_analysis,
                            "category_id": cat_id,
                            "sub_category_id": sub_cat_id,
                            "link_to_goal_id": goal_id,  # 新增: 关联的目标ID
                            "category": item.category,  # 保留用于调试
                            "sub_category": item.sub_category,  # 保留用于调试
                        }
                    )

        logger.info(
            "  [OK] 处理后保留 %s 条分类记录（原始 %s 条）",
            len(classified_records),
            len(result_items),
        )
        classified_app_df = pd.DataFrame(classified_records)

        # 验证分类结果
        logger.info("  验证分类结果...")
        classified_app_df = self._validate_classification_results(classified_app_df, category_tree)
        logger.info("  [OK] 验证完成")

        return classified_app_df

    def _validate_classification_results(
        self, df: pd.DataFrame, category_tree: dict
    ) -> pd.DataFrame:
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
            cat = df.at[idx, "category"]
            sub_cat = df.at[idx, "sub_category"]

            # 规则3: 两者都为None是合法的
            if pd.isna(cat) and pd.isna(sub_cat):
                continue

            # 规则4: A为None但B有值，不合法 -> 修正为都为None
            if pd.isna(cat) and not pd.isna(sub_cat):
                logger.warning(
                    "    [!] 索引 %s: 主分类为None但子分类为'%s'，修正为都为None", idx, sub_cat
                )
                df.at[idx, "sub_category"] = None
                invalid_count += 1
                continue

            # 规则2: A有值但B为None是合法的（A必须在分类树中）
            if not pd.isna(cat) and pd.isna(sub_cat):
                if cat not in category_tree:
                    logger.warning("    [!] 索引 %s: 主分类'%s'不在分类树中，修正为None", idx, cat)
                    df.at[idx, "category"] = None
                    invalid_count += 1
                continue

            # 规则1: A和B都有值，需要验证层级关系
            if not pd.isna(cat) and not pd.isna(sub_cat):
                # 检查主分类是否存在
                if cat not in category_tree:
                    logger.warning(
                        "    [!] 索引 %s: 主分类'%s'不在分类树中，修正为都为None", idx, cat
                    )
                    df.at[idx, "category"] = None
                    df.at[idx, "sub_category"] = None
                    invalid_count += 1
                    continue

                # 检查子分类是否属于该主分类
                if sub_cat not in category_tree[cat]:
                    logger.warning(
                        "    [!] 索引 %s: 子分类'%s'不属于主分类'%s'，"
                        "期望子分类为%s，修正为都为None",
                        idx,
                        sub_cat,
                        cat,
                        category_tree[cat],
                    )
                    df.at[idx, "category"] = None
                    df.at[idx, "sub_category"] = None
                    invalid_count += 1
                    continue

        if invalid_count > 0:
            logger.info("    修正了 %s 条不符合规则的分类结果", invalid_count)
        else:
            logger.info("    所有分类结果均符合规则")

        return df

    def _merge_classification_results(
        self, filtered_data: pd.DataFrame, classified_app_df: pd.DataFrame
    ) -> pd.DataFrame:
        """
        优化的分类结果合并逻辑（使用 pandas merge 替代 iterrows）

        使用 category_id 和 sub_category_id 进行合并（而非名称）

        注意: filtered_data 和 classified_app_df 中的 app/title 已经在数据清洗阶段
        （EventTransformer）全部格式化为小写，无需再次转换。

        Args:
            filtered_data: 过滤后的事件数据（app/title 已小写化）
            classified_app_df: 分类结果数据（app/title 已小写化）

        Returns:
            pd.DataFrame: 合并后的数据
        """
        logger.info("  使用向量化操作合并分类结果...")

        # 确保列存在
        if "category_id" not in filtered_data.columns:
            filtered_data["category_id"] = None
        if "sub_category_id" not in filtered_data.columns:
            filtered_data["sub_category_id"] = None
        if "link_to_goal_id" not in filtered_data.columns:
            filtered_data["link_to_goal_id"] = None

        # 分离单用途和多用途应用
        single_purpose = classified_app_df[classified_app_df["is_multipurpose_app"] == 0].copy()
        multi_purpose = classified_app_df[classified_app_df["is_multipurpose_app"] == 1].copy()

        # 处理单用途应用：只按 app 匹配
        # 注意: app 已在数据清洗阶段小写化，直接使用原字段匹配
        if not single_purpose.empty:
            # 只保留需要的列，避免列名冲突
            merge_cols = ["app", "category_id", "sub_category_id"]
            if "link_to_goal_id" in single_purpose.columns:
                merge_cols.append("link_to_goal_id")
            single_merge = single_purpose[merge_cols].rename(
                columns={
                    "category_id": "category_id_single",
                    "sub_category_id": "sub_category_id_single",
                    "link_to_goal_id": "link_to_goal_id_single",
                }
            )

            # 合并单用途应用的分类
            filtered_data = filtered_data.merge(single_merge, on="app", how="left")

            # 只更新单用途应用的分类（is_multipurpose_app == 0）
            mask_single = (filtered_data["is_multipurpose_app"] == 0) & (
                filtered_data["category_id_single"].notna()
            )
            filtered_data.loc[mask_single, "category_id"] = filtered_data.loc[
                mask_single, "category_id_single"
            ]
            filtered_data.loc[mask_single, "sub_category_id"] = filtered_data.loc[
                mask_single, "sub_category_id_single"
            ]
            if "link_to_goal_id_single" in filtered_data.columns:
                filtered_data.loc[mask_single, "link_to_goal_id"] = filtered_data.loc[
                    mask_single, "link_to_goal_id_single"
                ]

            # 删除临时列
            drop_cols = ["category_id_single", "sub_category_id_single"]
            if "link_to_goal_id_single" in filtered_data.columns:
                drop_cols.append("link_to_goal_id_single")
            filtered_data = filtered_data.drop(columns=drop_cols)

            logger.info("    [OK] 合并了 %s 个单用途应用的分类", mask_single.sum())

        # 处理多用途应用：按 (app, title) 匹配
        # 注意: app 和 title 已在数据清洗阶段小写化，直接使用原字段匹配
        if not multi_purpose.empty:
            # 只保留需要的列
            merge_cols = ["app", "title", "category_id", "sub_category_id"]
            if "link_to_goal_id" in multi_purpose.columns:
                merge_cols.append("link_to_goal_id")
            multi_merge = multi_purpose[merge_cols].rename(
                columns={
                    "category_id": "category_id_multi",
                    "sub_category_id": "sub_category_id_multi",
                    "link_to_goal_id": "link_to_goal_id_multi",
                }
            )

            # 合并多用途应用的分类
            filtered_data = filtered_data.merge(multi_merge, on=["app", "title"], how="left")

            # 只更新多用途应用的分类（is_multipurpose_app == 1）
            mask_multi = (filtered_data["is_multipurpose_app"] == 1) & (
                filtered_data["category_id_multi"].notna()
            )
            filtered_data.loc[mask_multi, "category_id"] = filtered_data.loc[
                mask_multi, "category_id_multi"
            ]
            filtered_data.loc[mask_multi, "sub_category_id"] = filtered_data.loc[
                mask_multi, "sub_category_id_multi"
            ]
            if "link_to_goal_id_multi" in filtered_data.columns:
                filtered_data.loc[mask_multi, "link_to_goal_id"] = filtered_data.loc[
                    mask_multi, "link_to_goal_id_multi"
                ]

            # 删除临时列
            drop_cols = ["category_id_multi", "sub_category_id_multi"]
            if "link_to_goal_id_multi" in filtered_data.columns:
                drop_cols.append("link_to_goal_id_multi")
            filtered_data = filtered_data.drop(columns=drop_cols)

            logger.info("    [OK] 合并了 %s 个多用途应用的分类", mask_multi.sum())

        # 统计
        total_classified = filtered_data["category_id"].notna().sum()
        logger.info("  [OK] 总共合并了 %s 条记录的分类", total_classified)

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
            category_id_to_name = {}
            if category is not None and not category.empty:
                category_dict = category.set_index("name")["id"].to_dict()
                category_id_to_name = category.set_index("id")["name"].to_dict()

            # 子分类使用复合 key (category_name, sub_category_name) -> sub_category_id
            sub_category_composite_dict = {}
            if sub_category is not None and not sub_category.empty:
                for _, row in sub_category.iterrows():
                    parent_cat_name = category_id_to_name.get(row["category_id"], "")
                    sub_category_composite_dict[(parent_cat_name, row["name"])] = row["id"]

            self._category_mappings_cache = {
                "category_id_dict": category_dict,
                "sub_category_composite_dict": sub_category_composite_dict,
            }
            logger.info("  [OK] 创建分类映射字典缓存")

        # 批量映射
        if "category" in filtered_data.columns:
            filtered_data["category_id"] = filtered_data["category"].map(
                self._category_mappings_cache["category_id_dict"]
            )
        if "sub_category" in filtered_data.columns and "category" in filtered_data.columns:
            # 使用复合 key (category, sub_category) 查找子分类 ID
            composite_dict = self._category_mappings_cache["sub_category_composite_dict"]
            filtered_data["sub_category_id"] = filtered_data.apply(
                lambda row: (
                    composite_dict.get((row.get("category"), row.get("sub_category")))
                    if pd.notna(row.get("sub_category"))
                    else None
                ),
                axis=1,
            )

        # 统计映射结果
        mapped_count = (
            filtered_data["category_id"].notna().sum()
            if "category_id" in filtered_data.columns
            else 0
        )
        logger.info("  [OK] 映射了 %s 条记录的分类 ID", mapped_count)

        return filtered_data

    def _save_tokens_usage(self, result: dict, result_items_count: int):
        """
        保存 token 使用数据到数据库（按天累加）

        Args:
            result: LLM 分类结果字典，包含 tokens_usage 信息
            result_items_count: 分类结果项目数
        """
        try:
            # 生成当天的 session_id（格式：c-YYYY-MM-DD），使用用户本地时区日期
            today = get_local_today().isoformat()
            session_id = f"c-{today}"

            # 从 result 中提取 tokens_usage 字典
            tokens_usage = result.get("tokens_usage", {})

            # 构造新的使用量数据
            new_usage = {
                "input_tokens": tokens_usage.get("input_tokens", 0),
                "output_tokens": tokens_usage.get("output_tokens", 0),
                "total_tokens": tokens_usage.get("total_tokens", 0),
                "search_count": tokens_usage.get("search_count", 0),
                "result_items_count": result_items_count,
                "mode": "classification",
            }

            # 读取已有数据并累加
            existing = tokens_usage_repository.get_tokens_usage_by_session_id(session_id)
            if existing:
                new_usage["input_tokens"] += existing.get("input_tokens", 0)
                new_usage["output_tokens"] += existing.get("output_tokens", 0)
                new_usage["total_tokens"] += existing.get("total_tokens", 0)
                new_usage["search_count"] += existing.get("search_count", 0)
                new_usage["result_items_count"] += existing.get("result_items_count", 0)

            # 保存到数据库
            tokens_usage_repository.upsert_tokens_usage(session_id, new_usage)
            logger.info(
                "  [OK] 保存 token 使用数据到 %s: input=%s, output=%s, total=%s",
                session_id,
                new_usage["input_tokens"],
                new_usage["output_tokens"],
                new_usage["total_tokens"],
            )

        except Exception as e:
            logger.error("保存 token 使用数据失败: error=%s", e)
            # 不抛出异常，避免影响主流程（辅助操作兜底）

    def clear_cache(self):
        """清除缓存的映射字典"""
        self._category_mappings_cache = None
        logger.info("已清除分类映射缓存")


if __name__ == "__main__":
    import asyncio

    async def _main():
        data_processing_service = DataProcessingService()
        datetime.now(timezone.utc) - timedelta(minutes=5)
        datetime.now(timezone.utc)
        await data_processing_service.process_activitywatch_data(auto_classify=True)

    asyncio.run(_main())
