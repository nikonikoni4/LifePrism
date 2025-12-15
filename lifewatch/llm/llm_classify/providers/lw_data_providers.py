"""
lifewatch数据提供者
为 LLM 分类模块提供数据库操作支持
"""
import pandas as pd
import logging
from typing import Set, Optional

from lifewatch.storage import lw_db_manager

logger = logging.getLogger(__name__)


class LWDataProviders:
    """
    LLM 数据提供者
    
    为 LLM 分类流程提供数据库操作支持
    """
    
    def __init__(self):
        self.db_manager = lw_db_manager

    def query_title_description(self, query_list: list[str]) -> list[dict[str, str]]:
        """查询标题描述"""
        sql = """
        SELECT key_word, description
        FROM title_description
        WHERE key_word IN ({})
        """.format(",".join(["?" for _ in query_list]))
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, query_list)
            results = cursor.fetchall()
        return [{"key_word": row[0], "description": row[1]} for row in results]

    def update_app_description(self, app_description_list: list[dict[str, str]]):
        """更新 app_description 表中的描述"""
        self.db_manager.upsert_many("app_purpose_category", app_description_list, "app")

    # ==================== 迁移自 LifeWatchDataManager 的方法 ====================
    
    def get_existing_apps(self) -> Set[str]:
        """
        从 app_purpose_category 表获取已存在的单一用途应用集合
        
        Returns:
            Set[str]: 应用名称集合（不包括多用途应用）
        """
        try:
            df = self.db_manager.query('app_purpose_category', 
                          columns=['app'],
                          where={'is_multipurpose_app': 0})
            existing_apps = set(df['app'].dropna().tolist()) if not df.empty else set()
            logger.info(f"从数据库获取到 {len(existing_apps)} 个已有应用")
            return existing_apps
        except Exception as e:
            logger.error(f"获取已有应用失败: {e}")
            return set()
    
    def load_app_purpose_category(self) -> Optional[pd.DataFrame]:
        """
        获取 app_purpose_category 表中的所有数据
        
        Returns:
            Optional[pd.DataFrame]: 包含所有应用分类数据的DataFrame，如果为空返回None
        """
        df = self.db_manager.query('app_purpose_category')
        return df if not df.empty else None


lw_data_providers = LWDataProviders()  # 全局唯一的实例


# ==================== 便捷函数（向后兼容）====================

def get_app_purpose_category() -> Optional[pd.DataFrame]:
    """
    便捷函数：获取应用用途分类
    
    Returns:
        Optional[pd.DataFrame]: 应用分类数据
    """
    return lw_data_providers.load_app_purpose_category()


if __name__ == "__main__":
    providers = LWDataProviders()
    print(f"已有应用数量: {len(providers.get_existing_apps())}")
    df = providers.load_app_purpose_category()
    if df is not None:
        print(f"应用分类数据行数: {len(df)}")
