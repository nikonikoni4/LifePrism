"""
待分类项收集器
负责收集未命中缓存的事件，构建 classifyState
"""

from lifeprism.llm import AppInFo, LogItem, classifyState
from lifeprism.processors.components.category_cache import CategoryCache
from lifeprism.processors.models.processed_event import ProcessedEvent
from lifeprism.utils import get_logger

logger = get_logger(__name__)


class ClassifyCollector:
    """
    待分类项收集器

    职责：
    - 收集未命中缓存的事件
    - 构建 app_registry 和 log_items
    - 实现去重逻辑：
      - 单用途应用：每个 app 只收集一次
      - 多用途应用：每个 title 收集一次
    """

    def __init__(self, cache: CategoryCache):
        """
        初始化收集器

        Args:
            cache: CategoryCache 实例，用于复用已有的应用描述
        """
        self.cache = cache

        # 应用注册表
        self._app_registry: dict[str, AppInFo] = {}

        # 待分类日志项
        self._log_items: list[LogItem] = []

        # 去重用的集合
        self._seen_apps: set[str] = set()  # 已见过的单用途 app
        self._seen_titles: set[str] = set()  # 已见过的多用途 title

        # ID 计数器
        self._id_counter = 0

    def collect(self, event: ProcessedEvent) -> None:
        """
        收集未命中缓存的事件

        Args:
            event: 待收集的事件
        """
        # 已命中缓存的事件不需要收集
        if event.cache_matched:
            return

        if not event.is_multipurpose:
            self._collect_single_purpose(event)
        else:
            self._collect_multipurpose(event)

    def _collect_single_purpose(self, event: ProcessedEvent) -> None:
        """
        收集单用途应用

        - 每个 app 只收集一次
        - 复用缓存中的应用描述
        """
        if event.app in self._seen_apps:
            return

        # 添加到应用注册表
        existing_desc = self.cache.get_app_description(event.app)
        self._app_registry[event.app] = AppInFo(
            description=existing_desc,  # 复用已有描述，空则待 LLM 填充
            is_multipurpose=False,
            titles=[event.title] if event.title else [],
        )
        self._seen_apps.add(event.app)

        # 创建 LogItem
        self._log_items.append(
            LogItem(id=self._id_counter, app=event.app, duration=event.duration, title=event.title)
        )
        self._id_counter += 1

        logger.debug("收集单用途应用: %s", event.app)

    def _collect_multipurpose(self, event: ProcessedEvent) -> None:
        """
        收集多用途应用

        - 每个 title 收集一次（同一 app 可能有多个 title）
        - 复用缓存中的应用描述
        """
        # 确保 app 在注册表中
        if event.app not in self._seen_apps:
            existing_desc = self.cache.get_app_description(event.app)
            self._app_registry[event.app] = AppInFo(
                description=existing_desc, is_multipurpose=True, titles=[]
            )
            self._seen_apps.add(event.app)

        # 检查 title 是否已收集
        if not event.title or event.title in self._seen_titles:
            return

        # 添加 title 到对应 app 的 titles 列表
        if self._app_registry[event.app].titles is not None:
            self._app_registry[event.app].titles.append(event.title)

        # 创建 LogItem
        self._log_items.append(
            LogItem(id=self._id_counter, app=event.app, duration=event.duration, title=event.title)
        )
        self._id_counter += 1
        self._seen_titles.add(event.title)

        logger.debug("收集多用途应用: %s - %s...", event.app, event.title[:30])

    def build_state(self) -> classifyState:
        """
        构建最终的 classifyState

        Returns:
            classifyState 对象
        """
        return classifyState(
            app_registry=self._app_registry, log_items=self._log_items, result_items=None
        )

    def get_stats(self) -> dict:
        """
        获取收集统计信息
        """
        single_count = sum(
            1
            for item in self._log_items
            if item.app in self._app_registry and not self._app_registry[item.app].is_multipurpose
        )
        multi_count = len(self._log_items) - single_count

        return {
            "total": len(self._log_items),
            "single": single_count,
            "multi": multi_count,
            "apps": len(self._app_registry),
        }

    def reset(self) -> None:
        """
        重置收集器状态
        """
        self._app_registry.clear()
        self._log_items.clear()
        self._seen_apps.clear()
        self._seen_titles.clear()
        self._id_counter = 0
