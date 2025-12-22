"""
LLM 模块专用数据提供者
继承 LWBaseDataProvider，添加 LLM 分类特定的数据库操作
"""
import pandas as pd
import logging
from typing import Set, Optional, List, Dict

from lifewatch.storage import LWBaseDataProvider

logger = logging.getLogger(__name__)


class LLMLWDataProvider(LWBaseDataProvider):
    """
    LLM 模块专用数据提供者
    
    继承 LWBaseDataProvider，添加 LLM 分类流程专用的数据库操作
    """
    
    def __init__(self, db_manager=None):
        """
        初始化 LLM 数据提供者
        
        Args:
            db_manager: DatabaseManager 实例，None 则使用全局单例
        """
        super().__init__(db_manager)
    
    # ==================== LLM 专用方法 ====================
    
    def query_title_description(self, query_list: List[str]) -> List[Dict[str, str]]:
        """
        查询标题描述
        
        Args:
            query_list: 关键词列表
            
        Returns:
            List[Dict]: 包含 key_word 和 description 的字典列表
        """
        if not query_list:
            return []
        
        sql = """
        SELECT key_word, description
        FROM title_analysis
        WHERE key_word IN ({})
        """.format(",".join(["?" for _ in query_list]))
        
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, query_list)
            results = cursor.fetchall()
        
        return [{"key_word": row[0], "description": row[1]} for row in results]
    
    def update_app_description(self, app_description_list: List[Dict[str, str]]) -> int:
        """
        更新应用描述
        
        Args:
            app_description_list: 应用描述数据列表
            
        Returns:
            int: 受影响的行数
        """
        return self.db.upsert_many("app_purpose_category", app_description_list, "app")

# 懒加载单例
from lifewatch.utils import LazySingleton
llm_lw_data_provider = LazySingleton(LLMLWDataProvider)