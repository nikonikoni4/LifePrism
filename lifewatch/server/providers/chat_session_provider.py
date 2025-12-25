"""
Chat Session Provider - 聊天会话元数据数据库操作

负责会话元数据的持久化存储
"""
from typing import List, Optional, Dict, Any
from datetime import datetime

from lifewatch.storage import LWBaseDataProvider
from lifewatch.utils import get_logger

logger = get_logger(__name__)


class ChatSessionProvider(LWBaseDataProvider):
    """会话元数据数据库操作类"""
    
    def __init__(self, db_manager=None):
        super().__init__(db_manager)
        self._table_name = 'chat_session'
    
    def get_all_sessions(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """
        获取所有会话，按更新时间降序
        
        Args:
            limit: 限制数量
            offset: 偏移量
            
        Returns:
            List[Dict]: 会话列表
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    f"""
                    SELECT id, name, message_count, created_at, updated_at
                    FROM {self._table_name}
                    ORDER BY updated_at DESC
                    LIMIT ? OFFSET ?
                    """,
                    (limit, offset)
                )
                
                columns = [description[0] for description in cursor.description]
                rows = cursor.fetchall()
                return [dict(zip(columns, row)) for row in rows]
                
        except Exception as e:
            logger.error(f"获取会话列表失败: {e}")
            return []
    
    def get_session_count(self) -> int:
        """获取会话总数"""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(f"SELECT COUNT(*) FROM {self._table_name}")
                return cursor.fetchone()[0]
        except Exception as e:
            logger.error(f"获取会话数量失败: {e}")
            return 0
    
    def get_session_by_id(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        根据 ID 获取会话
        
        Args:
            session_id: 会话 ID
            
        Returns:
            Dict 或 None
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    f"""
                    SELECT id, name, message_count, created_at, updated_at
                    FROM {self._table_name}
                    WHERE id = ?
                    """,
                    (session_id,)
                )
                row = cursor.fetchone()
                if row:
                    columns = [description[0] for description in cursor.description]
                    return dict(zip(columns, row))
                return None
                
        except Exception as e:
            logger.error(f"获取会话 {session_id} 失败: {e}")
            return None
    
    def create_session(
        self, 
        session_id: str, 
        name: str,
        created_at: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        创建新会话
        
        Args:
            session_id: 会话 ID
            name: 会话名称
            created_at: 创建时间（可选，默认当前时间）
            
        Returns:
            Dict: 创建的会话
        """
        now = created_at or datetime.now().isoformat()
        
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    f"""
                    INSERT INTO {self._table_name} 
                    (id, name, message_count, created_at, updated_at)
                    VALUES (?, ?, 0, ?, ?)
                    """,
                    (session_id, name, now, now)
                )
                
            logger.info(f"创建会话成功，ID: {session_id}")
            return {
                'id': session_id,
                'name': name,
                'message_count': 0,
                'created_at': now,
                'updated_at': now
            }
            
        except Exception as e:
            logger.error(f"创建会话失败: {e}")
            raise
    
    def update_session_name(self, session_id: str, name: str) -> bool:
        """
        更新会话名称
        
        Args:
            session_id: 会话 ID
            name: 新名称
            
        Returns:
            bool: 是否成功
        """
        now = datetime.now().isoformat()
        
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    f"""
                    UPDATE {self._table_name}
                    SET name = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (name, now, session_id)
                )
                return cursor.rowcount > 0
                
        except Exception as e:
            logger.error(f"更新会话名称失败: {e}")
            return False
    
    def increment_message_count(self, session_id: str) -> bool:
        """
        增加会话的消息计数
        
        Args:
            session_id: 会话 ID
            
        Returns:
            bool: 是否成功
        """
        now = datetime.now().isoformat()
        
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    f"""
                    UPDATE {self._table_name}
                    SET message_count = message_count + 1, updated_at = ?
                    WHERE id = ?
                    """,
                    (now, session_id)
                )
                return cursor.rowcount > 0
                
        except Exception as e:
            logger.error(f"更新消息计数失败: {e}")
            return False
    
    def delete_session(self, session_id: str) -> bool:
        """
        删除会话
        
        Args:
            session_id: 会话 ID
            
        Returns:
            bool: 是否成功
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    f"DELETE FROM {self._table_name} WHERE id = ?",
                    (session_id,)
                )
                success = cursor.rowcount > 0
                if success:
                    logger.info(f"删除会话 {session_id} 成功")
                return success
                
        except Exception as e:
            logger.error(f"删除会话失败: {e}")
            return False
    
    def session_exists(self, session_id: str) -> bool:
        """
        检查会话是否存在
        
        Args:
            session_id: 会话 ID
            
        Returns:
            bool: 是否存在
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    f"SELECT 1 FROM {self._table_name} WHERE id = ? LIMIT 1",
                    (session_id,)
                )
                return cursor.fetchone() is not None
                
        except Exception as e:
            logger.error(f"检查会话存在失败: {e}")
            return False


# 创建全局单例
_chat_session_provider: Optional[ChatSessionProvider] = None


def get_chat_session_provider() -> ChatSessionProvider:
    """获取 ChatSessionProvider 单例"""
    global _chat_session_provider
    if _chat_session_provider is None:
        _chat_session_provider = ChatSessionProvider()
    return _chat_session_provider
