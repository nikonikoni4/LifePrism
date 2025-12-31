"""
缓存索引管理器
负责从 DataFrame 构建高效的缓存索引，提供分类查询接口
"""
import pandas as pd
from typing import Dict, Set, Tuple, Optional
from lifewatch.utils import get_logger, DEBUG

logger = get_logger(__name__, DEBUG)


class CategoryCache:
    """
    分类缓存索引管理器
    
    职责：
    - 从 category_map_cache DataFrame 构建索引
    - 提供高效的缓存查询接口
    - 管理单用途/多用途应用的分类映射
    """
    
    def __init__(self, cache_df: Optional[pd.DataFrame] = None):
        """
        初始化缓存索引
        
        Args:
            cache_df: category_map_cache 表的 DataFrame
        """
        # 已分类的应用集合
        self._single_purpose_apps: Set[str] = set()
        self._multipurpose_apps: Set[str] = set()
        self._multipurpose_titles: Set[str] = set()
        
        # 分类映射: app/title -> (category_id, sub_category_id, link_to_goal_id)
        self._app_category_map: Dict[str, Tuple[str, Optional[str], Optional[str]]] = {}
        self._title_category_map: Dict[str, Tuple[str, Optional[str], Optional[str]]] = {}
        
        # 应用描述映射: app -> description
        self._app_description_map: Dict[str, str] = {}
        
        # 构建索引
        if cache_df is not None and not cache_df.empty:
            self._build_indexes(cache_df)
    
    def _build_indexes(self, cache_df: pd.DataFrame) -> None:
        """
        从 DataFrame 构建所有索引
        
        Args:
            cache_df: category_map_cache 表的 DataFrame
        """
        # 过滤有效记录（state=1 表示启用）
        if 'state' in cache_df.columns:
            valid_df = cache_df[cache_df['state'] == 1].copy()
        else:
            valid_df = cache_df.copy()
        
        logger.debug(f"构建缓存索引: 原始 {len(cache_df)} 行, 有效 {len(valid_df)} 行")
        
        # 分离单用途和多用途记录
        single_purpose_df = valid_df[valid_df['is_multipurpose_app'] == 0]
        multi_purpose_df = valid_df[valid_df['is_multipurpose_app'] == 1]
        
        # 只缓存有有效分类(category_id)的 app
        # 单用途：只有 category_id 不为空的 app 才被缓存
        single_with_category = single_purpose_df[single_purpose_df['category_id'].notna()]
        self._single_purpose_apps = set(single_with_category['app'].str.lower().dropna())
        
        # 多用途：只有 category_id 不为空且 title 不为空的才被缓存
        multi_with_category = multi_purpose_df[
            multi_purpose_df['category_id'].notna() & 
            multi_purpose_df['title'].notna()
        ]
        self._multipurpose_apps = set(multi_with_category['app'].str.lower().dropna())
        self._multipurpose_titles = set(multi_with_category['title'].str.lower().dropna())
        
        # 构建单用途应用分类映射（只处理有分类的记录）
        for _, row in single_with_category.iterrows():
            app = row.get('app', '')
            if app:
                app = app.lower()
                cat_id = row.get('category_id')
                sub_cat_id = row.get('sub_category_id')
                goal_id = row.get('link_to_goal_id')
                
                # 只添加第一个匹配（避免重复覆盖）
                if app not in self._app_category_map:
                    self._app_category_map[app] = (cat_id, sub_cat_id, goal_id)
        
        # 构建多用途应用分类映射（只处理有分类的记录）
        for _, row in multi_with_category.iterrows():
            title = row.get('title', '')
            if title:
                title = title.lower()
                cat_id = row.get('category_id')
                sub_cat_id = row.get('sub_category_id')
                goal_id = row.get('link_to_goal_id')
                
                if title not in self._title_category_map:
                    self._title_category_map[title] = (cat_id, sub_cat_id, goal_id)
        
        # 构建应用描述映射（使用完整 DataFrame，包括禁用的记录和无分类的记录）
        # app_description 只要存在就可以复用，与分类无关
        for _, row in cache_df.iterrows():
            app = row.get('app', '')
            desc = row.get('app_description', '')
            if app and desc:
                app = app.lower()
                if app not in self._app_description_map:
                    self._app_description_map[app] = desc
        
        logger.debug(
            f"索引构建完成: 单用途(有分类) {len(self._single_purpose_apps)} 个, "
            f"多用途(有分类) {len(self._multipurpose_apps)} 个, "
            f"titles(有分类) {len(self._multipurpose_titles)} 个, "
            f"描述 {len(self._app_description_map)} 个"
        )
    
    def get_single_purpose_category(self, app: str) -> Optional[Tuple[str, Optional[str], Optional[str]]]:
        """
        获取单用途应用的分类
        
        Args:
            app: 应用名称（应已小写化）
            
        Returns:
            (category_id, sub_category_id, link_to_goal_id) 或 None
        """
        return self._app_category_map.get(app)
    
    def get_multipurpose_category(self, app: str, title: str) -> Optional[Tuple[str, Optional[str], Optional[str]]]:
        """
        获取多用途应用的分类（基于 title）
        
        Args:
            app: 应用名称（应已小写化）
            title: 窗口标题（应已小写化）
            
        Returns:
            (category_id, sub_category_id, link_to_goal_id) 或 None
        """
        # 先检查 app 是否在多用途应用集合中
        if app not in self._multipurpose_apps:
            return None
        return self._title_category_map.get(title)
    
    def get_app_description(self, app: str) -> str:
        """
        获取应用描述（用于复用已有描述）
        
        Args:
            app: 应用名称（应已小写化）
            
        Returns:
            应用描述，如不存在则返回空字符串
        """
        return self._app_description_map.get(app, "")
    
    def is_single_purpose_cached(self, app: str) -> bool:
        """
        检查单用途应用是否已缓存（只缓存有分类的记录）
        
        Args:
            app: 应用名称（应已小写化）
        """
        return app in self._single_purpose_apps
    
    def is_multipurpose_app_cached(self, app: str) -> bool:
        """
        检查多用途应用是否已缓存（至少有一个 title 被分类过，只缓存有分类的记录）
        
        Args:
            app: 应用名称（应已小写化）
        """
        return app in self._multipurpose_apps
    
    def is_multipurpose_title_cached(self, app: str, title: str) -> bool:
        """
        检查多用途应用的特定 title 是否已缓存
        
        Args:
            app: 应用名称（应已小写化）
            title: 窗口标题（应已小写化）
        """
        return app in self._multipurpose_apps and title in self._multipurpose_titles
    
    def get_stats(self) -> dict:
        """
        获取缓存统计信息
        """
        return {
            'single_purpose_apps': len(self._single_purpose_apps),
            'multipurpose_apps': len(self._multipurpose_apps),
            'multipurpose_titles': len(self._multipurpose_titles),
            'app_descriptions': len(self._app_description_map),
        }


if __name__ == '__main__':
    from lifewatch.storage import LWBaseDataProvider
    lw_data_provider = LWBaseDataProvider()
    
    category_cache = CategoryCache(lw_data_provider.load_category_map_cache())
    print(category_cache.get_stats())