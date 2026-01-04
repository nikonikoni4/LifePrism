"""
任务池文件夹数据提供者
提供 TaskPoolFolder 的数据库操作
"""
from typing import Optional, List, Dict, Any

from lifeprism.storage import LWBaseDataProvider
from lifeprism.utils import get_logger

logger = get_logger(__name__)


class FolderProvider(LWBaseDataProvider):
    """
    任务池文件夹数据提供者
    
    继承 LWBaseDataProvider，提供文件夹的 CRUD 操作
    """
    
    def __init__(self, db_manager=None):
        super().__init__(db_manager)
    
    # ========================================================================
    # 文件夹 CRUD
    # ========================================================================
    
    def get_all_folders(self) -> List[Dict[str, Any]]:
        """
        获取所有文件夹
        
        Returns:
            List[Dict]: 文件夹列表，按 order_index 排序
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT id, name, order_index, is_expanded, created_at
                    FROM task_pool_folder
                    ORDER BY order_index ASC, id ASC
                """)
                rows = cursor.fetchall()
                return [
                    {
                        'id': row[0],
                        'name': row[1],
                        'order_index': row[2],
                        'is_expanded': bool(row[3]),
                        'created_at': row[4]
                    }
                    for row in rows
                ]
        except Exception as e:
            logger.error(f"获取文件夹列表失败: {e}")
            return []
    
    def get_folder_by_id(self, folder_id: int) -> Optional[Dict[str, Any]]:
        """
        按 ID 获取单个文件夹
        
        Args:
            folder_id: 文件夹 ID
        
        Returns:
            Optional[Dict]: 文件夹数据，不存在返回 None
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT id, name, order_index, is_expanded, created_at
                    FROM task_pool_folder
                    WHERE id = ?
                """, (folder_id,))
                row = cursor.fetchone()
                if row:
                    return {
                        'id': row[0],
                        'name': row[1],
                        'order_index': row[2],
                        'is_expanded': bool(row[3]),
                        'created_at': row[4]
                    }
                return None
        except Exception as e:
            logger.error(f"获取文件夹失败: {e}")
            return None
    
    def create_folder(self, name: str) -> Optional[int]:
        """
        创建文件夹
        
        Args:
            name: 文件夹名称
        
        Returns:
            Optional[int]: 新文件夹 ID，失败返回 None
        """
        try:
            with self.db.get_connection() as conn:
                # 获取当前最大 order_index
                cursor = conn.execute(
                    "SELECT COALESCE(MAX(order_index), -1) FROM task_pool_folder"
                )
                max_order = cursor.fetchone()[0]
                new_order = max_order + 1
                
                cursor = conn.execute("""
                    INSERT INTO task_pool_folder (name, order_index, is_expanded)
                    VALUES (?, ?, 1)
                """, (name, new_order))
                conn.commit()
                return cursor.lastrowid
        except Exception as e:
            logger.error(f"创建文件夹失败: {e}")
            return None
    
    def update_folder(self, folder_id: int, data: Dict[str, Any]) -> bool:
        """
        更新文件夹
        
        Args:
            folder_id: 文件夹 ID
            data: 要更新的字段 (name, is_expanded)
        
        Returns:
            bool: 是否成功
        """
        try:
            updates = []
            values = []
            
            for field in ['name', 'is_expanded']:
                if field in data and data[field] is not None:
                    updates.append(f"{field} = ?")
                    if field == 'is_expanded':
                        values.append(1 if data[field] else 0)
                    else:
                        values.append(data[field])
            
            if not updates:
                return True  # 无需更新
            
            values.append(folder_id)
            
            with self.db.get_connection() as conn:
                conn.execute(
                    f"UPDATE task_pool_folder SET {', '.join(updates)} WHERE id = ?",
                    values
                )
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"更新文件夹失败: {e}")
            return False
    
    def delete_folder(self, folder_id: int) -> bool:
        """
        删除文件夹
        
        注意：删除前应先将文件夹内的任务移出到根级别
        
        Args:
            folder_id: 文件夹 ID
        
        Returns:
            bool: 是否成功
        """
        try:
            with self.db.get_connection() as conn:
                # 先将文件夹内的任务移到根级别
                conn.execute(
                    "UPDATE todo_list SET folder_id = NULL WHERE folder_id = ?",
                    (folder_id,)
                )
                # 删除文件夹
                conn.execute(
                    "DELETE FROM task_pool_folder WHERE id = ?",
                    (folder_id,)
                )
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"删除文件夹失败: {e}")
            return False
    
    def reorder_folders(self, folder_ids: List[int]) -> bool:
        """
        批量更新文件夹排序
        
        Args:
            folder_ids: 文件夹 ID 列表（按新顺序排列）
        
        Returns:
            bool: 是否成功
        """
        try:
            with self.db.get_connection() as conn:
                for index, folder_id in enumerate(folder_ids):
                    conn.execute(
                        "UPDATE task_pool_folder SET order_index = ? WHERE id = ?",
                        (index, folder_id)
                    )
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"重排序文件夹失败: {e}")
            return False


# 单例模式
folder_provider = FolderProvider()
