"""
Being 数据提供者
提供 time_paradoxes 表的数据库操作（过去/现在/未来自我探索测试）
"""
import json
from typing import Optional, List, Dict, Any

from lifewatch.storage import LWBaseDataProvider
from lifewatch.utils import get_logger

logger = get_logger(__name__)


class BeingProvider(LWBaseDataProvider):
    """
    Being 模块数据提供者
    
    继承 LWBaseDataProvider，提供 time_paradoxes 表的 CRUD 操作
    使用 self.db 的通用方法进行数据库操作
    """
    
    TABLE_NAME = 'time_paradoxes'
    
    def __init__(self, db_manager=None):
        super().__init__(db_manager)
    
    # ==================== 查询操作 ====================
    
    def get_by_id(self, record_id: int) -> Optional[Dict[str, Any]]:
        """
        按 ID 获取单条记录
        
        Args:
            record_id: 记录 ID
        
        Returns:
            Optional[Dict]: 记录数据，不存在返回 None
        """
        try:
            result = self.db.get_by_id(self.TABLE_NAME, 'id', record_id)
            if result:
                return self._deserialize_content(result)
            return None
        except Exception as e:
            logger.error(f"获取记录 {record_id} 失败: {e}")
            return None
    
    def get_by_user_mode_version(
        self, 
        user_id: int, 
        mode: str, 
        version: int
    ) -> Optional[Dict[str, Any]]:
        """
        按用户ID、模式、版本号获取记录（唯一组合）
        
        Args:
            user_id: 用户 ID
            mode: 模式 (past/present/future)
            version: 版本号
        
        Returns:
            Optional[Dict]: 记录数据，不存在返回 None
        """
        try:
            df = self.db.query(
                self.TABLE_NAME,
                where={'user_id': user_id, 'mode': mode, 'version': version},
                limit=1
            )
            if df.empty:
                return None
            result = df.iloc[0].to_dict()
            return self._deserialize_content(result)
        except Exception as e:
            logger.error(f"获取记录失败 (user_id={user_id}, mode={mode}, version={version}): {e}")
            return None
    
    def get_all_by_user_mode(
        self, 
        user_id: int, 
        mode: str
    ) -> List[Dict[str, Any]]:
        """
        获取用户某模式下的所有版本记录
        
        Args:
            user_id: 用户 ID
            mode: 模式 (past/present/future)
        
        Returns:
            List[Dict]: 记录列表，按版本号降序排列
        """
        try:
            df = self.db.query(
                self.TABLE_NAME,
                where={'user_id': user_id, 'mode': mode},
                order_by='version DESC'
            )
            if df.empty:
                return []
            return [self._deserialize_content(row.to_dict()) for _, row in df.iterrows()]
        except Exception as e:
            logger.error(f"获取记录列表失败 (user_id={user_id}, mode={mode}): {e}")
            return []
    
    def get_latest_version(self, user_id: int, mode: str) -> int:
        """
        获取用户某模式下的最新版本号
        
        Args:
            user_id: 用户 ID
            mode: 模式 (past/present/future)
        
        Returns:
            int: 最新版本号，如果没有记录返回 0
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    f"SELECT MAX(version) FROM {self.TABLE_NAME} WHERE user_id = ? AND mode = ?",
                    (user_id, mode)
                )
                result = cursor.fetchone()
                return result[0] if result[0] is not None else 0
        except Exception as e:
            logger.error(f"获取最新版本号失败 (user_id={user_id}, mode={mode}): {e}")
            return 0
    
    def get_latest_record(self, user_id: int, mode: str) -> Optional[Dict[str, Any]]:
        """
        获取用户某模式下的最新版本记录
        
        Args:
            user_id: 用户 ID
            mode: 模式 (past/present/future)
        
        Returns:
            Optional[Dict]: 最新记录，不存在返回 None
        """
        try:
            df = self.db.query(
                self.TABLE_NAME,
                where={'user_id': user_id, 'mode': mode},
                order_by='version DESC',
                limit=1
            )
            if df.empty:
                return None
            result = df.iloc[0].to_dict()
            return self._deserialize_content(result)
        except Exception as e:
            logger.error(f"获取最新记录失败 (user_id={user_id}, mode={mode}): {e}")
            return None
    
    # ==================== 创建操作 ====================
    
    def create(self, data: Dict[str, Any]) -> Optional[int]:
        """
        创建新记录
        
        Args:
            data: 记录数据，包含 user_id, mode, version, content
        
        Returns:
            Optional[int]: 新记录 ID，失败返回 None
        """
        try:
            # 序列化 content 字段
            insert_data = self._serialize_content(data)
            
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                columns = ', '.join(insert_data.keys())
                placeholders = ', '.join(['?' for _ in insert_data])
                sql = f"INSERT INTO {self.TABLE_NAME} ({columns}) VALUES ({placeholders})"
                cursor.execute(sql, list(insert_data.values()))
                new_id = cursor.lastrowid
                logger.info(f"创建 Being 记录成功，ID: {new_id}")
                return new_id
        except Exception as e:
            logger.error(f"创建记录失败: {e}")
            return None
    
    def create_new_version(
        self, 
        user_id: int, 
        mode: str, 
        content: Dict[str, Any],
        ai_abstract: str = None
    ) -> Optional[Dict[str, Any]]:
        """
        创建新版本（自动递增版本号）
        
        Args:
            user_id: 用户 ID
            mode: 模式 (past/present/future)
            content: 测试内容
            ai_abstract: AI 总结（可选）
        
        Returns:
            Optional[Dict]: 创建的记录，失败返回 None
        """
        try:
            # 获取最新版本号并递增
            latest_version = self.get_latest_version(user_id, mode)
            new_version = latest_version + 1
            
            data = {
                'user_id': user_id,
                'mode': mode,
                'version': new_version,
                'content': content,
                'ai_abstract': ai_abstract
            }
            
            new_id = self.create(data)
            if new_id:
                return self.get_by_id(new_id)
            return None
        except Exception as e:
            logger.error(f"创建新版本失败: {e}")
            return None
    
    # ==================== 更新操作 ====================
    
    def update(self, record_id: int, data: Dict[str, Any]) -> bool:
        """
        更新记录
        
        Args:
            record_id: 记录 ID
            data: 要更新的字段
        
        Returns:
            bool: 是否成功
        """
        try:
            update_data = self._serialize_content(data)
            rows_affected = self.db.update(
                self.TABLE_NAME,
                update_data,
                where={'id': record_id}
            )
            if rows_affected > 0:
                logger.info(f"更新 Being 记录 {record_id} 成功")
                return True
            return False
        except Exception as e:
            logger.error(f"更新记录 {record_id} 失败: {e}")
            return False
    
    def update_by_user_mode_version(
        self, 
        user_id: int, 
        mode: str, 
        version: int,
        data: Dict[str, Any]
    ) -> bool:
        """
        按用户ID、模式、版本号更新记录
        
        Args:
            user_id: 用户 ID
            mode: 模式 (past/present/future)
            version: 版本号
            data: 要更新的字段
        
        Returns:
            bool: 是否成功
        """
        try:
            update_data = self._serialize_content(data)
            rows_affected = self.db.update(
                self.TABLE_NAME,
                update_data,
                where={'user_id': user_id, 'mode': mode, 'version': version}
            )
            if rows_affected > 0:
                logger.info(f"更新 Being 记录成功 (user_id={user_id}, mode={mode}, version={version})")
                return True
            return False
        except Exception as e:
            logger.error(f"更新记录失败: {e}")
            return False
    
    def upsert(
        self, 
        user_id: int, 
        mode: str, 
        version: int,
        content: Dict[str, Any],
        ai_abstract: str = None
    ) -> bool:
        """
        UPSERT 操作（存在则更新，不存在则插入）
        
        Args:
            user_id: 用户 ID
            mode: 模式 (past/present/future)
            version: 版本号
            content: 测试内容
            ai_abstract: AI 总结（可选）
        
        Returns:
            bool: 是否成功
        """
        try:
            data = {
                'user_id': user_id,
                'mode': mode,
                'version': version,
                'content': json.dumps(content, ensure_ascii=False) if isinstance(content, dict) else content,
                'ai_abstract': ai_abstract
            }
            
            self.db.upsert(
                self.TABLE_NAME,
                data,
                conflict_columns=['user_id', 'mode', 'version']
            )
            logger.info(f"UPSERT Being 记录成功 (user_id={user_id}, mode={mode}, version={version})")
            return True
        except Exception as e:
            logger.error(f"UPSERT 记录失败: {e}")
            return False
    
    # ==================== 删除操作 ====================
    
    def delete(self, record_id: int) -> bool:
        """
        删除记录
        
        Args:
            record_id: 记录 ID
        
        Returns:
            bool: 是否成功
        """
        try:
            rows_affected = self.db.delete(self.TABLE_NAME, where={'id': record_id})
            if rows_affected > 0:
                logger.info(f"删除 Being 记录 {record_id} 成功")
                return True
            return False
        except Exception as e:
            logger.error(f"删除记录 {record_id} 失败: {e}")
            return False
    
    def delete_by_user_mode_version(
        self, 
        user_id: int, 
        mode: str, 
        version: int
    ) -> bool:
        """
        按用户ID、模式、版本号删除记录
        
        Args:
            user_id: 用户 ID
            mode: 模式 (past/present/future)
            version: 版本号
        
        Returns:
            bool: 是否成功
        """
        try:
            rows_affected = self.db.delete(
                self.TABLE_NAME, 
                where={'user_id': user_id, 'mode': mode, 'version': version}
            )
            if rows_affected > 0:
                logger.info(f"删除 Being 记录成功 (user_id={user_id}, mode={mode}, version={version})")
                return True
            return False
        except Exception as e:
            logger.error(f"删除记录失败: {e}")
            return False
    
    # ==================== 辅助方法 ====================
    
    def _serialize_content(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        序列化 content 字段为 JSON 字符串
        """
        result = data.copy()
        if 'content' in result and isinstance(result['content'], dict):
            result['content'] = json.dumps(result['content'], ensure_ascii=False)
        return result
    
    def _deserialize_content(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        反序列化 content 字段为 Python 对象
        """
        result = data.copy()
        if 'content' in result and isinstance(result['content'], str):
            try:
                result['content'] = json.loads(result['content'])
            except json.JSONDecodeError:
                pass  # 保持原字符串
        return result


# 创建全局单例
being_provider = BeingProvider()
