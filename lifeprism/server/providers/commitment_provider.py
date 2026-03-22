"""
Commitment 数据提供者
提供 commitments 表的 CRUD 操作（含 LEFT JOIN user_values 获取 value_keyword）
"""
import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from lifeprism.storage import LWBaseDataProvider
from lifeprism.utils import get_logger, LazySingleton

logger = get_logger(__name__)


class CommitmentProvider(LWBaseDataProvider):
    """
    承诺模块数据提供者

    继承 LWBaseDataProvider，提供 commitments 的 CRUD 操作。
    """

    def __init__(self, db_manager=None):
        super().__init__(db_manager)

    def get_commitments(self, status: Optional[str] = None, value_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        获取承诺列表（LEFT JOIN user_values 获取 value_keywords）

        Args:
            status: 状态筛选，支持逗号分隔多值（如 "active,archived"）
            value_id: 按价值 ID 筛选

        Returns:
            List[Dict]: 承诺列表
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                conditions = []
                params = []

                if status:
                    status_list = [s.strip() for s in status.split(",")]
                    placeholders = ",".join(["?"] * len(status_list))
                    conditions.append(f"c.status IN ({placeholders})")
                    params.extend(status_list)

                if value_id:
                    conditions.append("c.value_id = ?")
                    params.append(value_id)

                where = f" WHERE {' AND '.join(conditions)}" if conditions else ""
                sql = f"""
                    SELECT c.*, v.keywords AS value_keywords
                    FROM commitments c
                    LEFT JOIN user_values v ON c.value_id = v.id
                    {where}
                    ORDER BY
                        CASE c.status WHEN 'active' THEN 0 WHEN 'archived' THEN 1 WHEN 'completed' THEN 2 END,
                        c.created_at DESC
                """
                cursor.execute(sql, params)
                columns = [desc[0] for desc in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"获取承诺列表失败: {e}")
            return []

    def get_commitment_by_id(self, commitment_id: str) -> Optional[Dict[str, Any]]:
        """
        按 ID 获取承诺（LEFT JOIN user_values 获取 value_keywords）

        Args:
            commitment_id: 承诺 ID (格式: cmt-xxx)

        Returns:
            Optional[Dict]: 承诺记录，不存在返回 None
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT c.*, v.keywords AS value_keywords
                    FROM commitments c
                    LEFT JOIN user_values v ON c.value_id = v.id
                    WHERE c.id = ?
                """, (commitment_id,))
                row = cursor.fetchone()
                if row:
                    columns = [desc[0] for desc in cursor.description]
                    return dict(zip(columns, row))
                return None
        except Exception as e:
            logger.error(f"获取承诺 {commitment_id} 失败: {e}")
            return None

    def get_commitments_by_value(self, value_id: str) -> List[Dict[str, Any]]:
        """
        获取某价值下的所有承诺（不 JOIN，用于 ValueDetailItem）

        Args:
            value_id: 价值 ID

        Returns:
            List[Dict]: 承诺列表
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id, content, status, created_at FROM commitments
                    WHERE value_id = ?
                    ORDER BY
                        CASE status WHEN 'active' THEN 0 WHEN 'archived' THEN 1 WHEN 'completed' THEN 2 END,
                        created_at DESC
                """, (value_id,))
                columns = [desc[0] for desc in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"获取价值 {value_id} 的承诺列表失败: {e}")
            return []

    def create_commitment(self, data: Dict[str, Any]) -> Optional[str]:
        """
        创建承诺

        Args:
            data: 承诺数据（需包含 content, value_id）

        Returns:
            Optional[str]: 新创建的 ID，失败返回 None
        """
        try:
            new_id = f"cmt-{str(uuid.uuid4())[:8]}"
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO commitments (id, content, value_id, status)
                    VALUES (?, ?, ?, 'active')
                """, (new_id, data['content'], data.get('value_id')))
            logger.info(f"创建承诺成功: {new_id}")
            return new_id
        except Exception as e:
            logger.error(f"创建承诺失败: {e}")
            return None

    def update_commitment(self, commitment_id: str, data: Dict[str, Any]) -> bool:
        """
        更新承诺（动态构建 SET，手动追加 updated_at）

        Args:
            commitment_id: 承诺 ID
            data: 要更新的字段

        Returns:
            bool: 是否成功
        """
        try:
            if not data:
                return True
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                allowed_fields = ['content', 'value_id', 'status']
                set_clauses = []
                values = []
                for key, value in data.items():
                    if key in allowed_fields:
                        set_clauses.append(f"{key} = ?")
                        values.append(value)
                if not set_clauses:
                    return True
                set_clauses.append("updated_at = ?")
                values.append(datetime.now(timezone.utc).isoformat())
                values.append(commitment_id)
                sql = f"UPDATE commitments SET {', '.join(set_clauses)} WHERE id = ?"
                cursor.execute(sql, values)
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"更新承诺 {commitment_id} 失败: {e}")
            return False

    def delete_commitment(self, commitment_id: str) -> bool:
        """
        删除承诺

        Args:
            commitment_id: 承诺 ID

        Returns:
            bool: 是否成功
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM commitments WHERE id = ?", (commitment_id,))
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"删除承诺 {commitment_id} 失败: {e}")
            return False


commitment_provider = LazySingleton(CommitmentProvider)

