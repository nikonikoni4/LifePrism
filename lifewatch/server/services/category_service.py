"""
分类管理服务层
实现分类的业务逻辑和数据库操作
"""

from typing import List, Dict, Optional, Any
from lifewatch.storage import lw_db_manager
from lifewatch.server.schemas.category_schemas import (
    CategoryDef, SubCategoryDef, CategoryResponse, SubCategoryResponse
)
import logging
import uuid

logger = logging.getLogger(__name__)


class CategoryService:
    """分类管理服务"""
    
    def __init__(self):
        """
        初始化分类服务，使用全局数据库单例
        """
        self.db = lw_db_manager
    
    def get_all_categories(self) -> List[Dict[str, Any]]:
        """
        获取所有分类（含子分类）
        
        Returns:
            List[Dict]: 分类列表，每个分类包含其子分类
        """
        try:
            # 查询所有主分类
            categories_df = self.db.query('category', order_by='order_index ASC')
            
            if categories_df.empty:
                logger.warning("没有找到任何分类数据")
                return []
            
            # 查询所有子分类
            sub_categories_df = self.db.query('sub_category', order_by='order_index ASC')
            
            # 构建分类树结构
            result = []
            for _, cat_row in categories_df.iterrows():
                category_id = cat_row['id']
                
                # 获取该分类的所有子分类
                sub_cats = []
                if not sub_categories_df.empty:
                    sub_cats_filtered = sub_categories_df[
                        sub_categories_df['category_id'] == category_id
                    ]
                    
                    for _, sub_row in sub_cats_filtered.iterrows():
                        sub_cats.append({
                            'id': sub_row['id'],
                            'name': sub_row['name']
                        })
                
                result.append({
                    'id': category_id,
                    'name': cat_row['name'],
                    'color': cat_row['color'],
                    'subCategories': sub_cats
                })
            
            logger.info(f"成功获取 {len(result)} 个分类")
            return result
            
        except Exception as e:
            logger.error(f"获取分类列表失败: {e}")
            raise
    
    def create_category(self, name: str, color: str) -> Dict[str, Any]:
        """
        创建新的主分类
        
        Args:
            name: 分类名称
            color: 分类颜色（十六进制格式）
            
        Returns:
            Dict: 创建的分类对象
        """
        try:
            # 生成唯一ID（使用短UUID）
            category_id = f"cat-{str(uuid.uuid4())[:8]}"
            
            # 获取当前最大的 order_index
            categories_df = self.db.query('category')
            max_order = 0
            if not categories_df.empty and 'order_index' in categories_df.columns:
                max_order = categories_df['order_index'].max()
            
            # 插入数据
            data = {
                'id': category_id,
                'name': name,
                'color': color,
                'order_index': max_order + 1
            }
            
            self.db.insert('category', data)
            logger.info(f"成功创建分类: {category_id} - {name}")
            
            return {
                'id': category_id,
                'name': name,
                'color': color,
                'subCategories': []
            }
            
        except Exception as e:
            logger.error(f"创建分类失败: {e}")
            raise
    
    def update_category(self, category_id: str, name: Optional[str] = None, 
                       color: Optional[str] = None) -> Dict[str, Any]:
        """
        更新主分类
        
        Args:
            category_id: 分类ID
            name: 新的分类名称（可选）
            color: 新的分类颜色（可选）
            
        Returns:
            Dict: 更新后的分类对象
            
        Raises:
            ValueError: 如果分类不存在
        """
        try:
            # 检查分类是否存在
            existing = self.db.get_by_id('category', 'id', category_id)
            if not existing:
                raise ValueError(f"分类 '{category_id}' 不存在")
            
            # 构建更新数据
            update_data = {}
            if name is not None:
                update_data['name'] = name
            if color is not None:
                update_data['color'] = color
            
            if not update_data:
                logger.warning("没有提供任何更新字段")
                return self._get_category_by_id(category_id)
            
            # 执行更新
            self.db.update_by_id('category', 'id', category_id, update_data)
            logger.info(f"成功更新分类: {category_id}")
            
            # 返回更新后的分类
            return self._get_category_by_id(category_id)
            
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"更新分类失败: {e}")
            raise
    
    def delete_category(self, category_id: str, 
                       reassign_to: str = 'other') -> bool:
        """
        删除主分类
        
        Args:
            category_id: 要删除的分类ID
            reassign_to: 重新分配关联记录到的分类ID（默认: 'other'）
            
        Returns:
            bool: 是否成功删除
            
        Raises:
            ValueError: 如果分类不存在
        """
        try:
            # 检查分类是否存在
            existing = self.db.get_by_id('category', 'id', category_id)
            if not existing:
                raise ValueError(f"分类 '{category_id}' 不存在")
            
            # 1. 重新分配关联的行为日志记录
            behavior_logs = self.db.query(
                'user_app_behavior_log',
                where={'category_id': category_id}
            )
            
            if not behavior_logs.empty:
                logger.info(f"找到 {len(behavior_logs)} 条关联记录，重新分配到 '{reassign_to}'")
                self.db.update(
                    'user_app_behavior_log',
                    {'category_id': reassign_to, 'sub_category_id': 'untracked'},
                    {'category_id': category_id}
                )
            
            # 2. 删除主分类（子分类会通过 CASCADE 自动删除）
            self.db.delete_by_id('category', 'id', category_id)
            logger.info(f"成功删除分类: {category_id}")
            
            return True
            
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"删除分类失败: {e}")
            raise
    
    def create_sub_category(self, category_id: str, name: str) -> Dict[str, Any]:
        """
        创建子分类
        
        Args:
            category_id: 所属主分类ID
            name: 子分类名称
            
        Returns:
            Dict: 创建的子分类对象
            
        Raises:
            ValueError: 如果主分类不存在
        """
        try:
            # 验证主分类存在
            existing_cat = self.db.get_by_id('category', 'id', category_id)
            if not existing_cat:
                raise ValueError(f"主分类 '{category_id}' 不存在")
            
            # 生成唯一ID
            sub_id = f"sub-{str(uuid.uuid4())[:8]}"
            
            # 获取当前最大的 order_index
            sub_cats_df = self.db.query(
                'sub_category',
                where={'category_id': category_id}
            )
            max_order = 0
            if not sub_cats_df.empty and 'order_index' in sub_cats_df.columns:
                max_order = sub_cats_df['order_index'].max()
            
            # 插入数据
            data = {
                'id': sub_id,
                'category_id': category_id,
                'name': name,
                'order_index': max_order + 1
            }
            
            self.db.insert('sub_category', data)
            logger.info(f"成功创建子分类: {sub_id} - {name}")
            
            return {
                'id': sub_id,
                'name': name
            }
            
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"创建子分类失败: {e}")
            raise
    
    def update_sub_category(self, category_id: str, sub_id: str, 
                           name: str) -> Dict[str, Any]:
        """
        更新子分类
        
        Args:
            category_id: 所属主分类ID
            sub_id: 子分类ID
            name: 新的子分类名称
            
        Returns:
            Dict: 更新后的子分类对象
            
        Raises:
            ValueError: 如果主分类或子分类不存在
        """
        try:
            # 验证主分类存在
            existing_cat = self.db.get_by_id('category', 'id', category_id)
            if not existing_cat:
                raise ValueError(f"主分类 '{category_id}' 不存在")
            
            # 验证子分类存在且属于该主分类
            existing_sub = self.db.get_by_id('sub_category', 'id', sub_id)
            if not existing_sub:
                raise ValueError(f"子分类 '{sub_id}' 不存在")
            
            if existing_sub['category_id'] != category_id:
                raise ValueError(f"子分类 '{sub_id}' 不属于分类 '{category_id}'")
            
            # 更新子分类
            self.db.update_by_id('sub_category', 'id', sub_id, {'name': name})
            logger.info(f"成功更新子分类: {sub_id}")
            
            return {
                'id': sub_id,
                'name': name
            }
            
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"更新子分类失败: {e}")
            raise
    
    def delete_sub_category(self, category_id: str, sub_id: str) -> bool:
        """
        删除子分类
        
        Args:
            category_id: 所属主分类ID
            sub_id: 子分类ID
            
        Returns:
            bool: 是否成功删除
            
        Raises:
            ValueError: 如果主分类或子分类不存在
        """
        try:
            # 验证主分类存在
            existing_cat = self.db.get_by_id('category', 'id', category_id)
            if not existing_cat:
                raise ValueError(f"主分类 '{category_id}' 不存在")
            
            # 验证子分类存在且属于该主分类
            existing_sub = self.db.get_by_id('sub_category', 'id', sub_id)
            if not existing_sub:
                raise ValueError(f"子分类 '{sub_id}' 不存在")
            
            if existing_sub['category_id'] != category_id:
                raise ValueError(f"子分类 '{sub_id}' 不属于分类 '{category_id}'")
            
            # 重新分配关联的行为日志记录
            behavior_logs = self.db.query(
                'user_app_behavior_log',
                where={'sub_category_id': sub_id}
            )
            
            if not behavior_logs.empty:
                logger.info(f"找到 {len(behavior_logs)} 条关联记录，重新分配到 'untracked'")
                self.db.update(
                    'user_app_behavior_log',
                    {'sub_category_id': 'untracked'},
                    {'sub_category_id': sub_id}
                )
            
            # 删除子分类
            self.db.delete_by_id('sub_category', 'id', sub_id)
            logger.info(f"成功删除子分类: {sub_id}")
            
            return True
            
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"删除子分类失败: {e}")
            raise
    
    def _get_category_by_id(self, category_id: str) -> Dict[str, Any]:
        """
        根据ID获取完整的分类对象（含子分类）
        
        Args:
            category_id: 分类ID
            
        Returns:
            Dict: 分类对象
        """
        category = self.db.get_by_id('category', 'id', category_id)
        if not category:
            raise ValueError(f"分类 '{category_id}' 不存在")
        
        # 获取子分类
        sub_cats_df = self.db.query(
            'sub_category',
            where={'category_id': category_id},
            order_by='order_index ASC'
        )
        
        sub_cats = []
        if not sub_cats_df.empty:
            for _, sub_row in sub_cats_df.iterrows():
                sub_cats.append({
                    'id': sub_row['id'],
                    'name': sub_row['name']
                })
        
        return {
            'id': category['id'],
            'name': category['name'],
            'color': category['color'],
            'subCategories': sub_cats
        }
