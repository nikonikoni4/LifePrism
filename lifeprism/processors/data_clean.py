"""
功能介绍: 接受aw的数据,依据单和多用途提取需要识别的item(重复内容跳过)

包含两个版本:
- clean_activitywatch_data: 原始版本（保留兼容）
- clean_activitywatch_data_v2: 重构版本（组件化架构）
"""

from datetime import datetime, timedelta

import pandas as pd
import pytz

from lifeprism.config import LOCAL_TIMEZONE
from lifeprism.config.database import get_table_columns
from lifeprism.config.settings_manager import settings
from lifeprism.llm import AppInFo, LogItem, classifyState
from lifeprism.processors import processor_aw_data_provider, processor_monitor_data_provider

# 导入重构组件
from lifeprism.processors.components import (
    CacheMatcher,
    CategoryCache,
    ClassifyCollector,
    EventTransformer,
)
from lifeprism.processors.models import ProcessedEvent
from lifeprism.repository import LWBaseDataProvider
from lifeprism.utils import get_logger, is_multipurpose_app

logger = get_logger(__name__)


def create_dict_from_table_columns(table_name: str, values: dict = None) -> dict:
    """
    根据数据库表配置动态创建字典

    Args:
        table_name: 表名，用于获取列配置
        values: 可选的字段值字典，未提供的字段默认为None

    Returns:
        dict: 包含所有表列的字典，未提供的值为None
    """
    columns = get_table_columns(table_name)
    result = {col: None for col in columns}
    if values:
        for key, value in values.items():
            if key in result:
                result[key] = value
    return result


def convert_utc_to_local(utc_timestamp_str: str, target_tz: str) -> str:
    """
    将ActivityWatch API返回的UTC时间戳转换为用户本地时间

    Args:
        utc_timestamp_str: API返回的UTC时间戳，格式如 "2025-11-19T08:14:52.000000+00:00"
        target_tz: 目标时区，默认为用户设置时区

    Rlifewatch.utils.py.utilss:
        str: 格式化后的本地时间字符串，格式如 "2025-11-19 16:14:52"

    Note:
        - 输入：ISO 8601格式的UTC时间戳
        - 输出：用户本地时区的格式化时间字符串
        - 保持毫秒级时间精度
    """
    try:
        # 1. 解析ISO 8601格式的UTC时间戳
        # 处理Z后缀（表示UTC）并替换为+00:00
        clean_timestamp = utc_timestamp_str.replace("Z", "+00:00")
        dt_utc = datetime.fromisoformat(clean_timestamp)

        # 2. 转换为用户指定的时区
        target_timezone = pytz.timezone(target_tz)
        dt_local = dt_utc.astimezone(target_timezone)

        # 3. 格式化输出，保持毫秒精度
        return dt_local.strftime("%Y-%m-%d %H:%M:%S")

    except Exception as e:
        # 错误处理：如果解析失败，返回原始字符串并记录警告
        # print(f"⚠️  时间戳转换失败: {utc_timestamp_str} -> {str(e)}")
        logger.warning("时间戳转换失败: %s -> %s", utc_timestamp_str, str(e))
        return utc_timestamp_str


def clean_activitywatch_data_old(
    start_time: datetime, end_time: datetime, category_map_cache_df: pd.DataFrame
) -> tuple[pd.DataFrame, classifyState]:
    """
    完整的数据清洗流程：从数据源获取数据 + 时间戳标准化 + 短活动过滤 + 数据库查询优化

    Args:
        start_time: 开始时间 (datetime 对象)
        end_time: 结束时间 (datetime 对象)
        category_map_cache_df: 应用目的分类DataFrame，包含category_map_cache_df表中的数据

    Returns:
        Tuple[pd.DataFrame, classifyState]:
            - filtered_events_df: 清洗后的事件数据DataFrame
            - classify_state: 包含待分类应用信息的classifyState对象
                - app_registry: 应用注册表 {app: AppInFo}
                - log_items: 待分类的日志项列表
                - result_items: 初始为None

    Process:
        1. 从指定数据源 (AW 或 内置) 获取原始事件
        2. 时间戳标准化：UTC -> 本地时间
        3. 短活动过滤：删除 < 60秒的事件
        4. 数据库查询：如果应用已存在分类数据，直接获取
        5. 构建classifyState：收集待分类应用的信息
    """
    # 从 ActivityWatch 获取原始数据
    raw_events = processor_aw_data_provider.get_window_events(
        start_time=start_time, end_time=end_time
    )

    logger.info("🧹 开始数据清洗流程...")
    logger.info("📥 原始数据: %d 个事件", len(raw_events))

    lower_bound = settings.data_cleaning_threshold
    removed_count = 0  # 初始化被过滤事件计数
    filtered_events_list = []  # 过滤后的事件列表

    # 已添加的待分类应用
    apps_to_classify_set = set()  # 已添加的待分类应用集合 用于判断是否已经添加
    title_to_classify_set = set()  # 已添加的待分类title集合 用于判断是否已经添加

    # classifyState 组件
    app_registry: dict[str, AppInFo] = {}  # 应用注册表
    log_items: list[LogItem] = []  # 待分类日志项
    log_item_id_counter = 0  # LogItem ID 计数器

    # 已经分类的应用（单一用途app和多用途title）
    # 以及已存在的app_description，避免LLM重复搜索
    logger.debug(
        "原始 category_map_cache_df 长度: %d",
        len(category_map_cache_df) if category_map_cache_df is not None else 0,
    )
    if category_map_cache_df is not None and not category_map_cache_df.empty:
        # 直接使用 state 字段过滤（state=0 表示对应的分类被禁用）
        valid_df = (
            category_map_cache_df[category_map_cache_df.get("state", 1) == 1].copy()
            if "state" in category_map_cache_df.columns
            else category_map_cache_df.copy()
        )
        logger.debug("过滤后的 valid_df 长度: %d", len(valid_df))
        # 获取已存在的单一用途的应用集合（只包含 is_multipurpose_app == 0 的）
        single_purpose_df = valid_df[valid_df["is_multipurpose_app"] == 0]
        categorized_single_purpose_apps = set(single_purpose_df["app"].unique())
        # 获取已存在的多用途应用集合（只包含 is_multipurpose_app == 1 的）
        multi_purpose_df = valid_df[valid_df["is_multipurpose_app"] == 1]
        categorized_multipurpose_apps = set(multi_purpose_df["app"].unique())
        # 获取非单一用途的title集合
        categorized_mutilpurpose_titles = set(multi_purpose_df["title"].unique())

        # 创建 app -> (category_id, sub_category_id, link_to_goal_id) 映射
        app_category_map: dict[str, tuple] = {}
        title_category_map: dict[str, tuple] = {}

        for _, row in valid_df.iterrows():
            app = row.get("app", "").lower()
            title_val = row.get("title", "").lower() if row.get("title") else ""
            cat_id = row.get("category_id")
            sub_cat_id = row.get("sub_category_id")
            goal_id = row.get("link_to_goal_id")  # 获取 link_to_goal_id
            is_multi = row.get("is_multipurpose_app", 0)
            if app == "antigravity":
                logger.debug("=" * 20)
                logger.debug("app: %s, goal_id: %s", app, goal_id)
                logger.debug("=" * 20)

            if app and cat_id:
                if is_multi == 0 and app not in app_category_map:
                    app_category_map[app] = (cat_id, sub_cat_id, goal_id)
                elif is_multi == 1 and title_val:
                    title_category_map[title_val] = (cat_id, sub_cat_id, goal_id)

        # 创建 app -> app_description 映射，用于复用已有的应用描述
        # 注意：统一转为小写，以匹配后续事件处理中的 app_name.lower()
        app_description_map: dict[str, str] = {}
        for _, row in category_map_cache_df.iterrows():
            app = row.get("app", "").lower()  # 统一转为小写
            desc = row.get("app_description", "")
            if app and desc and app not in app_description_map:
                app_description_map[app] = desc
    else:
        categorized_single_purpose_apps = set()
        categorized_multipurpose_apps = set()  # 新增
        categorized_mutilpurpose_titles = set()
        app_category_map = {}
        title_category_map = {}
        app_description_map = {}

    # output - 使用动态字典格式配置
    filtered_events_df = pd.DataFrame(columns=get_table_columns("user_app_behavior_log"))
    print(get_table_columns("user_app_behavior_log"))
    for event in raw_events:
        duration = int(event.get("duration", 0))
        if duration >= lower_bound:
            # 转换时间戳
            local_start_time = convert_utc_to_local(event.get("timestamp", ""), LOCAL_TIMEZONE)
            # 计算结束时间
            start_dt = datetime.strptime(local_start_time, "%Y-%m-%d %H:%M:%S")
            end_dt = start_dt + timedelta(seconds=duration)
            local_end_time = end_dt.strftime("%Y-%m-%d %H:%M:%S")
            # 获得应用名称
            app_name = event.get("data", {}).get("app", None)

            if app_name:
                app_name = app_name.lower().strip().split(".exe")[0]
                # 获得title
                title = event.get("data", {}).get("title", None)
                if title:
                    title = title.split("和另外")[0].strip().lower()

                is_multipurpose = is_multipurpose_app(app_name)

                # 使用动态字典创建事件数据
                filtered_event = create_dict_from_table_columns(
                    "user_app_behavior_log",
                    {
                        "id": event.get("id", ""),
                        "start_time": local_start_time,
                        "end_time": local_end_time,
                        "duration": duration,
                        "app": app_name,
                        "title": title,
                        "is_multipurpose_app": 1 if is_multipurpose else 0,
                    },
                )

                # 1.app已经被分类 且 app是单一用途的 ： 直接进行分类
                if app_name in categorized_single_purpose_apps and not is_multipurpose:
                    # 对于单一应用，直接从映射获取分类ID
                    cat_ids = app_category_map.get(app_name)
                    if cat_ids:
                        filtered_event["category_id"] = cat_ids[0]
                        filtered_event["sub_category_id"] = cat_ids[1]
                        filtered_event["link_to_goal_id"] = cat_ids[2] if len(cat_ids) > 2 else None
                        logger.debug(
                            "✅ 成功获取分类数据: category_id=%s, sub_category_id=%s, link_to_goal_id=%s",
                            cat_ids[0],
                            cat_ids[1],
                            cat_ids[2] if len(cat_ids) > 2 else None,
                        )

                # 2.多用途app已经被分类 且 对应的title也有分类记录 ： 根据title获取分类
                elif (
                    app_name in categorized_multipurpose_apps
                    and title
                    and title in categorized_mutilpurpose_titles
                ):
                    # 对于多应用场景，根据title匹配分类数据
                    cat_ids = title_category_map.get(title)
                    if cat_ids:
                        filtered_event["category_id"] = cat_ids[0]
                        filtered_event["sub_category_id"] = cat_ids[1]
                        filtered_event["link_to_goal_id"] = cat_ids[2] if len(cat_ids) > 2 else None
                        logger.debug(
                            "✅ 成功获取分类数据: category_id=%s, sub_category_id=%s, link_to_goal_id=%s",
                            cat_ids[0],
                            cat_ids[1],
                            cat_ids[2] if len(cat_ids) > 2 else None,
                        )
                        logger.debug("✅ 多用途匹配成功: app_name=%s, title=%s", app_name, title)
                # 3. app未被分类，且是单一用途的
                elif not is_multipurpose:
                    # 3.1 app未被分类，且是单一用途的 且 未被添加到待分类列表 ： 加入待分类列表
                    # 一个app只需要加入一次，只创建一个LogItem
                    if app_name not in apps_to_classify_set:
                        # 添加到 app_registry，复用已存在的app_description
                        existing_desc = app_description_map.get(app_name, "")
                        app_registry[app_name] = AppInFo(
                            description=existing_desc,  # 复用已有描述，空则待LLM填充
                            is_multipurpose=False,
                            titles=[title],
                        )
                        apps_to_classify_set.add(app_name)

                        # 创建 LogItem 并添加到 log_items（每个单用途app只需一个）
                        log_items.append(
                            LogItem(
                                id=log_item_id_counter,
                                app=app_name,
                                duration=int(duration),
                                title=title,
                            )
                        )
                        log_item_id_counter += 1

                # 4.app未被分类，且是多用途的 ： 加入待分类列表
                elif is_multipurpose:
                    # 确保 app 在 registry 中
                    if app_name not in apps_to_classify_set:
                        # 复用已存在的app_description
                        existing_desc = app_description_map.get(app_name, "")
                        app_registry[app_name] = AppInFo(
                            description=existing_desc,  # 复用已有描述，空则待LLM填充
                            is_multipurpose=True,
                            titles=[],
                        )
                        apps_to_classify_set.add(app_name)

                    # 4.1 app未被分类，且是多用途的 且 未被添加到待分类列表 ： 加入待分类列表
                    # 特别的，使用title进行分类，一个title添加一次，app名称可重复
                    if title and title not in title_to_classify_set:
                        # 添加 title 到对应 app 的 titles 列表
                        if app_registry[app_name].titles is not None:
                            app_registry[app_name].titles.append(title)

                        # 创建 LogItem 并添加到 log_items
                        log_items.append(
                            LogItem(
                                id=log_item_id_counter,
                                app=app_name,
                                duration=int(duration),
                                title=title,
                            )
                        )
                        log_item_id_counter += 1
                        title_to_classify_set.add(title)

                # 使用列表收集所有事件，最后一次性创建DataFrame
                filtered_events_list.append(filtered_event)
        else:
            # 记录被过滤的短暂活动
            removed_count += 1

    # 一次性创建DataFrame，避免循环中的concat警告
    if filtered_events_list:
        filtered_events_df = pd.DataFrame(filtered_events_list)
        # 去重：ActivityWatch 可能返回重复事件（相同 app + timestamp）
        before_count = len(filtered_events_df)
        filtered_events_df = filtered_events_df.drop_duplicates(
            subset=["app", "start_time"], keep="first"
        )
        after_count = len(filtered_events_df)
        if before_count != after_count:
            logger.info(
                "[DEDUP] 去除重复事件: %d -> %d (移除 %d 条)",
                before_count,
                after_count,
                before_count - after_count,
            )

    # 构建 classifyState
    classify_state = classifyState(
        app_registry=app_registry, log_items=log_items, result_items=None
    )

    # 统计日志
    single_count = len(
        [
            item
            for item in log_items
            if not app_registry.get(
                item.app, AppInFo(description="", is_multipurpose=False)
            ).is_multipurpose
        ]
    )
    multi_count = len(
        [
            item
            for item in log_items
            if app_registry.get(
                item.app, AppInFo(description="", is_multipurpose=False)
            ).is_multipurpose
        ]
    )

    logger.info(
        "[STAT] 过滤统计: 总事件 %d -> 保留 %d -> 删除 %d",
        len(raw_events),
        len(filtered_events_df),
        removed_count,
    )
    logger.info(
        "[STAT] 待分类统计: 总项目 %d -> 单用途 %d -> 多用途 %d",
        len(log_items),
        single_count,
        multi_count,
    )
    logger.info("[STAT] 应用注册表: %d 个应用", len(app_registry))
    return filtered_events_df, classify_state


# ============================================================================
# 重构版本 - 组件化架构
# ============================================================================


def _events_to_dataframe(events: list[ProcessedEvent]) -> pd.DataFrame:
    """
    将 ProcessedEvent 列表转换为 DataFrame

    Args:
        events: ProcessedEvent 列表

    Returns:
        包含事件数据的 DataFrame
    """
    if not events:
        return pd.DataFrame(columns=get_table_columns("user_app_behavior_log"))
    print(events[0].to_dict().keys())
    return pd.DataFrame([event.to_dict() for event in events])


def _process_events_batch(
    raw_events: list[dict],
    cache: "CategoryCache",
    transformer: "EventTransformer",
    matcher: "CacheMatcher",
    collector: "ClassifyCollector",
) -> tuple[list[ProcessedEvent], int]:
    """
    处理一批原始事件数据

    执行以下操作：
    1. 转换事件（时间戳标准化、短活动过滤）
    2. 匹配缓存分类
    3. 收集待分类项

    Args:
        raw_events: 原始事件列表（来自 ActivityWatch）
        cache: CategoryCache 实例
        transformer: EventTransformer 实例
        matcher: CacheMatcher 实例
        collector: ClassifyCollector 实例

    Returns:
        Tuple[List[ProcessedEvent], int]:
            - events: 处理后的事件列表
            - removed_count: 被过滤的事件数量
    """
    # 1. 转换事件
    events, removed_count = transformer.transform_batch(raw_events)

    # 2. 匹配缓存 & 收集待分类项
    for event in events:
        matcher.match(event)  # 匹配后的数据标记 cache_matched = True
        collector.collect(event)

    return events, removed_count


# 默认批次大小：50,000 条事件
DEFAULT_BATCH_SIZE = 50000


def clean_activitywatch_data(
    start_time: datetime,
    end_time: datetime,
    category_map_cache_df: pd.DataFrame,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> tuple[pd.DataFrame, classifyState]:
    """
    完整的数据清洗流程（重构版本 - 组件化架构 + 分批处理）

    与原版本 clean_activitywatch_data 功能相同，但使用组件化设计：
    - CategoryCache: 缓存索引管理
    - EventTransformer: 事件转换与标准化
    - CacheMatcher: 缓存匹配策略
    - ClassifyCollector: 待分类项收集

    支持分批处理大数据量，避免内存问题。

    Args:
        start_time: 开始时间 (datetime 对象)
        end_time: 结束时间 (datetime 对象)
        category_map_cache_df: 分类缓存 DataFrame
        batch_size: 每批处理的事件数量，默认 50,000

    Returns:
        Tuple[pd.DataFrame, classifyState]:
            - filtered_events_df: 清洗后的事件数据 DataFrame
            - classify_state: 包含待分类应用信息的 classifyState 对象
    """
    logger.info("🧹 开始数据清洗流程 (v2)...")

    # 1. 获取原始数据
    # 根据监控类型选择 Provider
    if settings.monitor_type == "lifeprism":
        logger.info("使用内置监控数据源 (lifeprism)")
        raw_events = processor_monitor_data_provider.get_window_events(
            start_time=start_time, end_time=end_time
        )
    elif settings.monitor_type == "none":
        logger.info("监控已禁用 (monitor_type=none)，跳过数据获取")
        raw_events = []
    else:
        logger.info("使用 ActivityWatch 数据源")
        raw_events = processor_aw_data_provider.get_window_events(
            start_time=start_time, end_time=end_time
        )
    total_events = len(raw_events)
    logger.info("📥 原始数据: %d 个事件", total_events)

    # 2. 初始化组件（全局共享，跨批次累积状态）
    cache = CategoryCache(category_map_cache_df)
    transformer = EventTransformer()
    matcher = CacheMatcher(cache)
    collector = ClassifyCollector(cache)

    logger.debug("📦 缓存统计: %s", cache.get_stats())

    # 3. 分批处理
    all_events: list[ProcessedEvent] = []
    total_removed = 0

    if total_events <= batch_size:
        # 数据量较小，直接处理
        events, removed_count = _process_events_batch(
            raw_events, cache, transformer, matcher, collector
        )
        all_events = events
        total_removed = removed_count
        logger.debug("🔄 事件转换完成: 有效 %d, 过滤 %d", len(events), removed_count)
    else:
        # 数据量较大，分批处理
        num_batches = (total_events + batch_size - 1) // batch_size
        logger.info("📦 数据量较大，分 %d 批处理 (每批 %d 条)", num_batches, batch_size)

        for batch_idx in range(num_batches):
            batch_start = batch_idx * batch_size
            batch_end = min(batch_start + batch_size, total_events)
            batch_events = raw_events[batch_start:batch_end]

            events, removed_count = _process_events_batch(
                batch_events, cache, transformer, matcher, collector
            )
            all_events.extend(events)
            total_removed += removed_count

            logger.debug(
                "  批次 %d/%d: 处理 %d 条, 有效 %d, 过滤 %d",
                batch_idx + 1,
                num_batches,
                len(batch_events),
                len(events),
                removed_count,
            )

    # 4. 构建输出
    filtered_events_df = _events_to_dataframe(all_events)
    classify_state = collector.build_state()

    # 5. 日志统计
    match_stats = matcher.get_stats()
    collect_stats = collector.get_stats()

    logger.info(
        "[STAT] 过滤统计: 总事件 %d -> 保留 %d -> 删除 %d",
        total_events,
        len(all_events),
        total_removed,
    )
    logger.info(
        "[STAT] 缓存匹配: 命中 %d, 未命中 %d", match_stats["matched"], match_stats["missed"]
    )
    logger.info(
        "[STAT] 待分类统计: 总项目 %d -> 单用途 %d -> 多用途 %d",
        collect_stats["total"],
        collect_stats["single"],
        collect_stats["multi"],
    )
    logger.info("[STAT] 应用注册表: %d 个应用", collect_stats["apps"])

    return filtered_events_df, classify_state


if __name__ == "__main__":

    def test_v1_and_v2():
        from datetime import timedelta

        # 测试时间范围
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=24)  # 测试24小时数据

        # 加载缓存数据
        category_map_cache_df = LWBaseDataProvider().load_category_map_cache_V2()
        print(f"缓存数据: {len(category_map_cache_df)} 行")

        print("\n" + "=" * 60)
        print("测试原版本 (v1)")
        print("=" * 60)
        filtered_events_df_v1, classify_state_v1 = clean_activitywatch_data_old(
            start_time, end_time, category_map_cache_df
        )
        print(f"过滤后事件数: {len(filtered_events_df_v1)}")
        print(f"待分类应用: {list(classify_state_v1.app_registry.keys())}")
        print(f"待分类日志项数: {len(classify_state_v1.log_items)}")

        print("\n" + "=" * 60)
        print("测试重构版本 (v2)")
        print("=" * 60)
        filtered_events_df_v2, classify_state_v2 = clean_activitywatch_data(
            start_time, end_time, category_map_cache_df
        )
        print(f"过滤后事件数: {len(filtered_events_df_v2)}")
        print(f"待分类应用: {list(classify_state_v2.app_registry.keys())}")
        print(f"待分类日志项数: {len(classify_state_v2.log_items)}")

        # 对比结果
        print("\n" + "=" * 60)
        print("结果对比")
        print("=" * 60)
        print(f"事件数一致: {len(filtered_events_df_v1) == len(filtered_events_df_v2)}")
        print(
            f"待分类数一致: {len(classify_state_v1.log_items) == len(classify_state_v2.log_items)}"
        )
        print(
            f"应用数一致: {len(classify_state_v1.app_registry) == len(classify_state_v2.app_registry)}"
        )

        # 详细对比应用
        v1_apps = set(classify_state_v1.app_registry.keys())
        v2_apps = set(classify_state_v2.app_registry.keys())
        if v1_apps != v2_apps:
            print(f"v1 独有: {v1_apps - v2_apps}")
            print(f"v2 独有: {v2_apps - v1_apps}")
        else:
            print("应用集合完全一致 [OK]")

    def special_test():
        """
        特殊测试：使用模拟数据测试数据清洗组件

        测试 category_map_cache_df 数据：
        | id | app | title | description | 分类 | 单/多用途 |
        | :--- | :--- | :--- | :--- | :--- | :--- |
        | 1 | single_app0 | None | None | None | 单用途 | (非法数据: 无title)
        | 2 | single_app1 | None | single_app1_des | None | 单用途 |
        | 3 | single_app2 | single_app2_title | None | None | 单用途 |
        | 4 | single_app3 | single_app3_title | single_app3_des | None | 单用途 |
        | 5 | single_app4 | single_app4_title | single_app4_des | (cat-work, sub-coding, goal-project) | 单用途 |
        | 6 | multi_app0 | None | None | None | 多用途 | (非法数据: 无title)
        | 7 | multi_app1 | None | multi_app1_des | None | 多用途 | (非法数据: 无title)
        | 8 | multi_app2 | multi_app2_title | None | None | 多用途 |
        | 9 | multi_app3 | multi_app3_title | multi_app3_des | None | 多用途 |
        | 10 | multi_app4 | multi_app4_title | multi_app4_des | (cat-entertainment, sub-tv, None) | 多用途 |
        """
        import pandas as pd

        from lifeprism.processors.components import (
            CacheMatcher,
            CategoryCache,
            ClassifyCollector,
        )
        from lifeprism.processors.models import ProcessedEvent

        print("\n" + "=" * 70)
        print("特殊测试: 模拟数据测试")
        print("=" * 70)

        # ========================================
        # 1. 构建模拟的 category_map_cache_df
        # ========================================
        cache_data = [
            # id=1: 单用途，无title无description无分类 (边界)
            {
                "id": 1,
                "app": "single_app0",
                "title": None,
                "is_multipurpose_app": 0,
                "app_description": None,
                "category_id": None,
                "sub_category_id": None,
                "link_to_goal_id": None,
                "state": 1,
            },
            # id=2: 单用途，无title有description无分类
            {
                "id": 2,
                "app": "single_app1",
                "title": None,
                "is_multipurpose_app": 0,
                "app_description": "single_app1_des",
                "category_id": None,
                "sub_category_id": None,
                "link_to_goal_id": None,
                "state": 1,
            },
            # id=3: 单用途，有title无description无分类
            {
                "id": 3,
                "app": "single_app2",
                "title": "single_app2_title",
                "is_multipurpose_app": 0,
                "app_description": None,
                "category_id": None,
                "sub_category_id": None,
                "link_to_goal_id": None,
                "state": 1,
            },
            # id=4: 单用途，有title有description无分类
            {
                "id": 4,
                "app": "single_app3",
                "title": "single_app3_title",
                "is_multipurpose_app": 0,
                "app_description": "single_app3_des",
                "category_id": None,
                "sub_category_id": None,
                "link_to_goal_id": None,
                "state": 1,
            },
            # id=5: 单用途，完整数据，有分类
            {
                "id": 5,
                "app": "single_app4",
                "title": "single_app4_title",
                "is_multipurpose_app": 0,
                "app_description": "single_app4_des",
                "category_id": "cat-work",
                "sub_category_id": "sub-coding",
                "link_to_goal_id": "goal-project",
                "state": 1,
            },
            # id=6: 多用途，无title无description无分类 (边界)
            {
                "id": 6,
                "app": "multi_app0",
                "title": None,
                "is_multipurpose_app": 1,
                "app_description": None,
                "category_id": None,
                "sub_category_id": None,
                "link_to_goal_id": None,
                "state": 1,
            },
            # id=7: 多用途，无title有description无分类
            {
                "id": 7,
                "app": "multi_app1",
                "title": None,
                "is_multipurpose_app": 1,
                "app_description": "multi_app1_des",
                "category_id": None,
                "sub_category_id": None,
                "link_to_goal_id": None,
                "state": 1,
            },
            # id=8: 多用途，有title无description无分类
            {
                "id": 8,
                "app": "multi_app2",
                "title": "multi_app2_title",
                "is_multipurpose_app": 1,
                "app_description": None,
                "category_id": None,
                "sub_category_id": None,
                "link_to_goal_id": None,
                "state": 1,
            },
            # id=9: 多用途，有title有description无分类
            {
                "id": 9,
                "app": "multi_app3",
                "title": "multi_app3_title",
                "is_multipurpose_app": 1,
                "app_description": "multi_app3_des",
                "category_id": None,
                "sub_category_id": None,
                "link_to_goal_id": None,
                "state": 1,
            },
            # id=10: 多用途，完整数据，有分类
            {
                "id": 10,
                "app": "multi_app4",
                "title": "multi_app4_title",
                "is_multipurpose_app": 1,
                "app_description": "multi_app4_des",
                "category_id": "cat-entertainment",
                "sub_category_id": "sub-tv",
                "link_to_goal_id": None,
                "state": 1,
            },
        ]
        category_map_cache_df = pd.DataFrame(cache_data)

        print("\n[1] 构建的 category_map_cache_df:")
        print(
            category_map_cache_df[
                ["id", "app", "title", "is_multipurpose_app", "category_id"]
            ].to_string()
        )

        # ========================================
        # 2. 测试 CategoryCache 构建
        # ========================================
        print("\n[2] 测试 CategoryCache 构建:")
        cache = CategoryCache(category_map_cache_df)
        stats = cache.get_stats()
        print(f"  缓存统计: {stats}")

        # 验证单用途缓存 (只有 id=5 有有效分类)
        print(f"\n  单用途 single_app4 缓存命中: {cache.is_single_purpose_cached('single_app4')}")
        print(f"  单用途 single_app4 分类: {cache.get_single_purpose_category('single_app4')}")
        print(
            f"  单用途 single_app0 缓存命中: {cache.is_single_purpose_cached('single_app0')}"
        )  # 无分类
        print(f"  单用途 single_app1 描述复用: '{cache.get_app_description('single_app1')}'")

        # 验证多用途缓存 (只有 id=10 有有效分类)
        print(
            f"\n  多用途 multi_app4 + title 缓存命中: {cache.is_multipurpose_title_cached('multi_app4', 'multi_app4_title')}"
        )
        print(
            f"  多用途 multi_app4 + title 分类: {cache.get_multipurpose_category('multi_app4', 'multi_app4_title')}"
        )
        print(
            f"  多用途 multi_app0 缓存命中: {cache.is_multipurpose_app_cached('multi_app0')}"
        )  # 无title
        print(f"  多用途 multi_app1 描述复用: '{cache.get_app_description('multi_app1')}'")

        # ========================================
        # 3. 测试 CacheMatcher
        # ========================================
        print("\n[3] 测试 CacheMatcher:")
        matcher = CacheMatcher(cache)

        # 测试事件列表
        test_events = [
            # 单用途，有缓存分类
            ProcessedEvent(
                id="e1",
                app="single_app4",
                title="any_title",
                is_multipurpose=False,
                start_time="2025-12-31 09:00:00",
                end_time="2025-12-31 09:05:00",
                duration=300,
            ),
            # 单用途，无缓存分类
            ProcessedEvent(
                id="e2",
                app="single_app1",
                title="any_title",
                is_multipurpose=False,
                start_time="2025-12-31 09:05:00",
                end_time="2025-12-31 09:10:00",
                duration=300,
            ),
            # 单用途，完全新应用
            ProcessedEvent(
                id="e3",
                app="new_single_app",
                title="new_title",
                is_multipurpose=False,
                start_time="2025-12-31 09:10:00",
                end_time="2025-12-31 09:15:00",
                duration=300,
            ),
            # 多用途，有缓存分类
            ProcessedEvent(
                id="e4",
                app="multi_app4",
                title="multi_app4_title",
                is_multipurpose=True,
                start_time="2025-12-31 09:15:00",
                end_time="2025-12-31 09:20:00",
                duration=300,
            ),
            # 多用途，app在缓存但title不在
            ProcessedEvent(
                id="e5",
                app="multi_app4",
                title="new_title_for_multi_app4",
                is_multipurpose=True,
                start_time="2025-12-31 09:20:00",
                end_time="2025-12-31 09:25:00",
                duration=300,
            ),
            # 多用途，完全新应用
            ProcessedEvent(
                id="e6",
                app="new_multi_app",
                title="new_multi_title",
                is_multipurpose=True,
                start_time="2025-12-31 09:25:00",
                end_time="2025-12-31 09:30:00",
                duration=300,
            ),
        ]

        for event in test_events:
            matcher.match(event)
            status = "HIT" if event.cache_matched else "MISS"
            print(
                f"  [{status}] {event.app} | title={event.title[:25]}... | cat={event.category_id}"
            )

        print(f"\n  匹配统计: {matcher.get_stats()}")

        # ========================================
        # 4. 测试 ClassifyCollector
        # ========================================
        print("\n[4] 测试 ClassifyCollector:")
        collector = ClassifyCollector(cache)

        for event in test_events:
            collector.collect(event)

        state = collector.build_state()
        print(f"  收集统计: {collector.get_stats()}")
        print(f"  待分类应用: {list(state.app_registry.keys())}")
        print(f"  待分类日志项数: {len(state.log_items)}")

        print("\n  待分类日志项详情:")
        for item in state.log_items:
            app_info = state.app_registry.get(item.app)
            multi_str = "多用途" if app_info and app_info.is_multipurpose else "单用途"
            desc = app_info.description if app_info else ""
            print(
                f"    id={item.id} | {multi_str} | app={item.app} | title={item.title} | desc='{desc}'"
            )

        print("\n" + "=" * 70)
        print("测试完成!")
        print("=" * 70)

    # 运行测试
    test_v1_and_v2()
    # special_test()
