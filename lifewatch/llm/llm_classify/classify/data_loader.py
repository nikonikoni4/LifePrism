"""
数据加载器
用于从 LifeWatch 数据库加载真实数据并转换为 classifyState 格式
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

from lifewatch.llm.llm_classify.providers import LLMLWDataProvider
from lifewatch.server.providers.statistical_data_providers import ServerLWDataProvider
from lifewatch.llm.llm_classify.schemas.classify_shemas import classifyState, LogItem, AppInFo, Goal
from lifewatch.llm.llm_classify.classify.mock_data import mock_goals as _mock_goals_raw
from lifewatch.utils import is_multipurpose_app
from lifewatch import config

# 将 langchain_test 的 Goal 对象转换为 llm_classify 的 Goal 类型
mock_goals = [Goal(goal=g.goal, category=g.category, sub_category=g.sub_category) for g in _mock_goals_raw]

logger = logging.getLogger(__name__)


class DataLoader:
    """
    数据加载器
    
    从 LifeWatch 数据库获取真实用户行为数据，
    并转换为 classifyState 格式供 LangGraph 使用
    """
    
    def __init__(self):
        """
        初始化数据加载器
        
        使用全局单例数据提供者
        """
        self.lw_data_provider = LLMLWDataProvider()
        self.stat_provider = ServerLWDataProvider()
    
    def get_real_data(self, hours: int = 24) -> tuple[classifyState, list[Goal], dict[str, list[str] | None]]:
        """
        获取真实数据并转换为 classifyState
        
        Args:
            hours: 获取最近N小时的数据
            
        Returns:
            tuple: (classifyState, goals, category_tree)
                - classifyState: 包含 app_registry, log_items, result_items
                - goals: 用户目标列表
                - category_tree: 分类树
        """
        logger.info(f"开始加载最近 {hours} 小时的数据...")
        
        # 1. 加载行为日志
        log_items = self._load_log_items(hours)
        logger.info(f"  ✓ 加载了 {len(log_items)} 条行为日志")
        
        # 2. 构建应用注册表
        app_registry = self._build_app_registry(log_items)
        logger.info(f"  ✓ 构建了 {len(app_registry)} 个应用的注册表")
        
        # 3. 构建分类树
        category_tree = self._build_category_tree()
        logger.info(f"  ✓ 构建了分类树，共 {len(category_tree)} 个主分类")
        
        # 4. 使用 mock_goals
        goals = mock_goals
        logger.info(f"  ✓ 使用 mock_goals，共 {len(goals)} 个目标")
        
        # 构建状态 (不再包含 goal 和 category_tree)
        state = classifyState(
            app_registry=app_registry,
            log_items=log_items
        )
        
        logger.info(f"数据加载完成！")
        return state, goals, category_tree
    
    def _load_log_items(self, hours: int) -> list[LogItem]:
        """
        从数据库加载行为日志并转换为 LogItem 列表
        
        Args:
            hours: 获取最近N小时的数据
            
        Returns:
            list[LogItem]: 行为日志列表
        """
        # 计算时间范围
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=hours)
        
        start_time_str = start_time.strftime('%Y-%m-%d %H:%M:%S')
        end_time_str = end_time.strftime('%Y-%m-%d %H:%M:%S')
        
        # 从数据库加载数据
        df = self.stat_provider.load_user_app_behavior_log(
            start_time=start_time_str,
            end_time=end_time_str
        )
        
        if df is None or df.empty:
            logger.warning("未找到行为日志数据")
            return []
        
        # 转换为 LogItem 列表
        log_items = []
        for _, row in df.iterrows():
            log_item = LogItem(
                id=row.get('id', 0),
                app=row.get('app', ''),
                duration=int(row.get('duration', 0)),
                title=row.get('title', None),
                title_analysis=None,  # 初始化为 None，后续由搜索节点填充
                category=None,  # 测试用：设置为 None
                sub_category=None,  # 测试用：设置为 None
                link_to_goal=None
            )
            log_items.append(log_item)
        
        return log_items
    
    def _build_app_registry(self, log_items: list[LogItem]) -> dict[str, AppInFo]:
        """
        构建应用注册表
        
        从 app_purpose_category 表获取应用描述，
        对于没有描述的应用，设置为空字符串
        同时从 log_items 中收集每个应用的典型 titles 样本
        
        Args:
            log_items: 行为日志列表，用于确定需要哪些应用
            
        Returns:
            dict[str, AppInFo]: 应用名称到应用信息的映射
        """
        # 获取所有唯一应用名称
        unique_apps = set(item.app for item in log_items)
        
        # 从数据库加载应用分类数据
        app_category_df = self.lw_data_provider.load_app_purpose_category()
        
        # 为每个 app 收集 titles 样本（最多5个非空且不重复的title）
        app_titles_map = {}
        for item in log_items:
            if item.app not in app_titles_map:
                app_titles_map[item.app] = []
            # 收集非空且不重复的 title，最多5个
            if item.title and item.title not in app_titles_map[item.app]:
                if len(app_titles_map[item.app]) < 5:
                    app_titles_map[item.app].append(item.title)
        
        # 构建注册表
        app_registry = {}
        for app_name in unique_apps:
            description = ""
            is_multipurpose = is_multipurpose_app(app_name)
            titles = app_titles_map.get(app_name, None) or None  # 空列表转为 None
            
            # 尝试从数据库获取描述
            if app_category_df is not None and not app_category_df.empty:
                app_row = app_category_df[app_category_df['app'].str.lower() == app_name.lower()]
                if not app_row.empty:
                    description = app_row.iloc[0].get('app_description', '') or ''
            
            app_registry[app_name] = AppInFo(
                description=description,
                is_multipurpose=is_multipurpose,
                titles=titles
            )
        
        return app_registry
    
    def _build_category_tree(self) -> dict[str, list[str] | None]:
        """
        构建分类树
        
        从 category 和 sub_category 表构建分类树结构
        
        Returns:
            dict[str, list[str] | None]: 主分类到子分类列表的映射
        """
        # 加载分类数据
        category_df = self.stat_provider.load_categories()
        sub_category_df = self.stat_provider.load_sub_categories()
        
        if category_df is None or category_df.empty:
            logger.warning("未找到分类数据，使用默认分类树")
            return {
                "工作/学习": ["编程", "学习AI相关知识", "记笔记"],
                "娱乐": ["游戏", "看电视"],
                "其他": None,
            }
        
        # 构建分类树
        category_tree = {}
        for _, cat_row in category_df.iterrows():
            cat_id = cat_row['id']
            cat_name = cat_row['name']
            
            # 找到属于该主分类的所有子分类
            if sub_category_df is not None and not sub_category_df.empty:
                subs = sub_category_df[sub_category_df['category_id'] == cat_id]['name'].tolist()
                category_tree[cat_name] = subs if subs else None
            else:
                category_tree[cat_name] = None
        
        return category_tree


# 便捷函数
def get_real_data(hours: int = 24) -> tuple[classifyState, list[Goal], dict[str, list[str] | None]]:
    """
    便捷函数：获取真实数据
    
    Args:
        hours: 获取最近N小时的数据
        
    Returns:
        tuple: (classifyState, goals, category_tree)
    """
    loader = DataLoader()
    return loader.get_real_data(hours=hours)


def filter_by_duration(
    state: classifyState, 
    min_duration: Optional[int] = None, 
    max_duration: Optional[int] = None
) -> classifyState:
    """
    按 duration 过滤 classifyState 中的 log_items
    
    Args:
        state: 原始的 classifyState 对象
        min_duration: 最小时长（秒），None 表示不限制
        max_duration: 最大时长（秒），None 表示不限制
        
    Returns:
        classifyState: 过滤后的新状态对象
        
    Example:
        # 只保留 duration >= 60 秒的记录
        filtered_state = filter_by_duration(state, min_duration=60)
        
        # 只保留 60 <= duration <= 300 的记录
        filtered_state = filter_by_duration(state, min_duration=60, max_duration=300)
    """
    # 过滤 log_items
    filtered_log_items = []
    for item in state.log_items:
        # 检查最小时长
        if min_duration is not None and item.duration < min_duration:
            continue
        # 检查最大时长
        if max_duration is not None and item.duration > max_duration:
            continue
        filtered_log_items.append(item)
    
    # 重新构建 app_registry（只包含过滤后的应用）
    filtered_apps = set(item.app for item in filtered_log_items)
    filtered_app_registry = {
        app: info 
        for app, info in state.app_registry.items() 
        if app in filtered_apps
    }
    
    # 创建新的 classifyState (不再包含 goal 和 category_tree)
    filtered_state = classifyState(
        app_registry=filtered_app_registry,
        log_items=filtered_log_items
    )
    
    logger.info(f"过滤完成: {len(state.log_items)} -> {len(filtered_log_items)} 条记录")
    
    return filtered_state


def deduplicate_log_items(state: classifyState) -> classifyState:
    """
    对 log_items 进行去重
    
    规则：
    - 单用途 app (is_multipurpose=False): 只保留一条记录（取 duration 最长的）
    - 多用途 app (is_multipurpose=True): 只保留 title 不同的记录（每个 title 取 duration 最长的）
    
    Args:
        state: 原始的 classifyState 对象
        
    Returns:
        classifyState: 去重后的新状态对象
        
    Example:
        state = get_real_data(hours=2)
        dedup_state = deduplicate_log_items(state)
    """
    # 按 app 分组
    app_groups = {}
    for item in state.log_items:
        if item.app not in app_groups:
            app_groups[item.app] = []
        app_groups[item.app].append(item)
    
    deduplicated_items = []
    
    for app_name, items in app_groups.items():
        # 获取 app 信息
        app_info = state.app_registry.get(app_name)
        if not app_info:
            # 如果没有 app 信息，保留所有记录
            deduplicated_items.extend(items)
            continue
        
        if not app_info.is_multipurpose:
            # 单用途 app：只保留 duration 最长的一条
            longest_item = max(items, key=lambda x: x.duration)
            deduplicated_items.append(longest_item)
        else:
            # 多用途 app：按 title 分组，每个 title 保留 duration 最长的一条
            title_groups = {}
            for item in items:
                title = item.title or ""  # 处理 None 的情况
                if title not in title_groups:
                    title_groups[title] = []
                title_groups[title].append(item)
            
            # 每个 title 保留 duration 最长的一条
            for title_items in title_groups.values():
                longest_item = max(title_items, key=lambda x: x.duration)
                deduplicated_items.append(longest_item)
    
    # 重新构建 app_registry（只包含去重后的应用）
    dedup_apps = set(item.app for item in deduplicated_items)
    dedup_app_registry = {
        app: info 
        for app, info in state.app_registry.items() 
        if app in dedup_apps
    }
    
    # 创建新的 classifyState (不再包含 goal 和 category_tree)
    dedup_state = classifyState(
        app_registry=dedup_app_registry,
        log_items=deduplicated_items
    )
    
    logger.info(f"去重完成: {len(state.log_items)} -> {len(deduplicated_items)} 条记录")
    
    return dedup_state


if __name__ == "__main__":
    # 测试数据加载
    import logging
    logging.basicConfig(level=logging.INFO)
    
    state, goals, category_tree = get_real_data(hours=36)
    state = filter_by_duration(state, min_duration=60)
    print(f"\n加载结果:")
    print(f"  - log_items: {len(state.log_items)} 条")
    print(f"  - app_registry: {len(state.app_registry)} 个应用")
    print(f"  - category_tree: {category_tree}")
    print(f"  - goals: {len(goals)} 个目标")
    
    # 打印前5条日志
    print(f"\n前5条日志:")
    for item in state.log_items[:5]:
        print(f"  {item.app} | {item.title} | {item.duration}s")
    
    # 测试去重功能
    print(f"\n测试去重功能:")
    dedup_state = deduplicate_log_items(state)
    print(f"  - 去重后 log_items: {len(dedup_state.log_items)} 条")
    print(f"  - 去重后 app_registry: {len(dedup_state.app_registry)} 个应用")
    
    # 打印去重后的数据（前10条）
    print(f"\n去重后的日志（前10条）:")
    for item in dedup_state.log_items[:10]:
        multipurpose = "多用途" if dedup_state.app_registry[item.app].is_multipurpose else "单用途"
        print(f"  {item.app} ({multipurpose}) | {item.title} | {item.duration}s")
    
    # 测试过滤功能
    print(f"\n测试过滤功能（只保留 duration >= 60 秒的记录）:")
    filtered_state = filter_by_duration(state, min_duration=60)
    print(f"  - 过滤后 log_items: {len(filtered_state.log_items)} 条")
    print(f"  - 过滤后 app_registry: {len(filtered_state.app_registry)} 个应用")
