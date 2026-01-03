"""
缓存匹配器
负责使用缓存索引匹配事件的分类
"""
from lifewatch.processors.models.processed_event import ProcessedEvent
from lifewatch.processors.components.category_cache import CategoryCache
from lifewatch.utils import get_logger, DEBUG

logger = get_logger(__name__)


class CacheMatcher:
    """
    缓存匹配器
    
    职责：
    - 尝试从缓存中匹配事件的分类
    - 根据单用途/多用途使用不同的匹配策略
    - 填充匹配成功的分类信息
    """
    
    def __init__(self, cache: CategoryCache):
        """
        初始化匹配器
        
        Args:
            cache: CategoryCache 实例
        """
        self.cache = cache
        self._match_count = 0
        self._miss_count = 0
    
    def match(self, event: ProcessedEvent) -> ProcessedEvent:
        """
        尝试从缓存匹配分类
        
        - 成功：填充 category_id 等字段，设置 cache_matched=True
        - 失败：保持原样
        
        Args:
            event: 待匹配的事件
            
        Returns:
            更新后的事件（原地修改）
        """
        if not event.is_multipurpose:
            self._match_single_purpose(event)
        else:
            self._match_multipurpose(event)
        
        return event
    
    def _match_single_purpose(self, event: ProcessedEvent) -> None:
        """
        单用途应用匹配
        
        - 基于应用名称匹配
        - 同一个 app 所有事件使用相同分类
        """
        category = self.cache.get_single_purpose_category(event.app)
        if category:
            event.category_id = category[0]
            event.sub_category_id = category[1]
            event.link_to_goal_id = category[2]
            event.cache_matched = True
            self._match_count += 1
            logger.debug(
                f"✅ 单用途缓存命中: app={event.app}, "
                f"category={category[0]}, sub={category[1]}"
            )
        else:
            self._miss_count += 1
    
    def _match_multipurpose(self, event: ProcessedEvent) -> None:
        """
        多用途应用匹配
        
        - 基于 app + title 组合匹配
        - 同一个 app 不同 title 可能有不同分类
        """
        # 首先检查 app 是否在多用途缓存中
        if not self.cache.is_multipurpose_app_cached(event.app):
            self._miss_count += 1
            return
        
        category = self.cache.get_multipurpose_category(event.app, event.title)
        if category:
            event.category_id = category[0]
            event.sub_category_id = category[1]
            event.link_to_goal_id = category[2]
            event.cache_matched = True
            self._match_count += 1
            logger.debug(
                f"✅ 多用途缓存命中: app={event.app}, title={event.title[:30]}..., "
                f"category={category[0]}, sub={category[1]}"
            )
        else:
            # app 在缓存中但 title 没有，仍然算 miss
            self._miss_count += 1
    
    def get_stats(self) -> dict:
        """
        获取匹配统计信息
        """
        return {
            'matched': self._match_count,
            'missed': self._miss_count,
            'total': self._match_count + self._miss_count,
        }
    
    def reset_stats(self) -> None:
        """
        重置统计信息
        """
        self._match_count = 0
        self._miss_count = 0

if __name__ == "__main__":
    from lifewatch.processors.components.category_cache import CategoryCache
    from lifewatch.processors.models.processed_event import ProcessedEvent
    from lifewatch.storage import LWBaseDataProvider
    lw_data_provider = LWBaseDataProvider()
    cache = CategoryCache(lw_data_provider.load_category_map_cache_V2())
    print(cache.is_multipurpose_title_cached("msedge", "lifewatchai"))
    matcher = CacheMatcher(cache)
    event = ProcessedEvent(id=1,app="msedge", title="lifewatchai", is_multipurpose=1, start_time="2025-12-31 08:38:00", end_time="2025-12-31 08:38:00", duration=10)
    matcher.match(event)
    print(matcher.get_stats())