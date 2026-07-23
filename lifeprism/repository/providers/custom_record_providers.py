"""
Custom Record Providers - 自定义记录元数据表的数据提供者

为 custom_record_types 和 custom_record_fields 两张 SYNC_TABLES 提供 Provider，
使 CustomRecordRepository.delete_type 能通过 _generic_* 通道删除（含写墓碑）。

表特征：
- 均为 TEXT 主键表（id 格式：crt-{uuid[:8]} / crf-{uuid[:8]}）
- 均在 SYNC_TABLES 中（删除时写墓碑，墓碑 record_id = 主键值）
- 不在 HASH_ID_PREFIXES 中（无 hash_id 字段）

设计约束：
- CustomRecordRepository 本身不继承 LWBaseDataProvider（动态表名运行时才确定）
- 但 meta 表（custom_record_types/custom_record_fields）是静态表，可走 _generic_* 通道
- 因此单独创建 Provider 类承载 meta 表的 _generic_* 调用
"""

import sqlite3

from lifeprism.repository.base_providers import LWBaseDataProvider
from lifeprism.utils import get_logger
from lifeprism.utils.exceptions import DataAccessError

logger = get_logger(__name__)


# ==================== CustomRecordTypeProvider ====================


class CustomRecordTypeProvider(LWBaseDataProvider):
    """自定义记录类型数据提供者（对应 custom_record_types 表）

    职责：为 custom_record_types 表提供 _generic_delete 通道（含写墓碑）。
    CustomRecordRepository.delete_type 通过此 Provider 删除类型记录。
    """

    # ==================== 表元数据定义 ====================

    _TABLE_NAME = "custom_record_types"
    _PRIMARY_KEY = "id"
    _DATE_FIELD = None
    _TIME_FIELD = None
    _ON_CONFLICT = "abort"

    _FILTER_FIELDS: set[str] = {
        "id",
        "name",
        "slug",
        "created_at",
        "updated_at",
    }
    _ORDER_FIELDS: set[str] = {"id", "name", "created_at"}
    _SELECT_FIELDS: set[str] = {
        "id",
        "name",
        "slug",
        "description",
        "card_template",
        "icon",
        "accent_color",
        "created_at",
        "updated_at",
    }
    _UPDATE_FIELDS: set[str] = {
        "name",
        "slug",
        "description",
        "card_template",
        "icon",
        "accent_color",
    }

    def __init__(self, db_manager=None):
        super().__init__(db_manager)

    # ==================== 删除方法 ====================

    def delete(self, type_id: str) -> bool:
        """
        删除类型记录（走 _generic_delete 通道，含写墓碑）

        供 CustomRecordRepository.delete_type 调用。

        Args:
            type_id: 类型 ID

        Returns:
            是否成功
        """
        try:
            return self._generic_delete(type_id)
        except DataAccessError:
            raise
        except sqlite3.Error as e:
            logger.error("删除自定义记录类型失败: type_id=%s, error=%s", type_id, e)
            raise DataAccessError(f"删除自定义记录类型失败: {e}") from e


# ==================== CustomRecordFieldProvider ====================


class CustomRecordFieldProvider(LWBaseDataProvider):
    """自定义记录字段数据提供者（对应 custom_record_fields 表）

    职责：为 custom_record_fields 表提供 _generic_batch_delete 通道（含写墓碑）。
    CustomRecordRepository.delete_type 通过此 Provider 批量删除字段记录。
    """

    # ==================== 表元数据定义 ====================

    _TABLE_NAME = "custom_record_fields"
    _PRIMARY_KEY = "id"
    _DATE_FIELD = None
    _TIME_FIELD = None
    _ON_CONFLICT = "abort"

    _FILTER_FIELDS: set[str] = {
        "id",
        "type_id",
        "field_key",
        "field_type",
        "sort_order",
        "created_at",
    }
    _ORDER_FIELDS: set[str] = {"id", "sort_order", "created_at"}
    _SELECT_FIELDS: set[str] = {
        "id",
        "type_id",
        "field_name",
        "field_key",
        "field_type",
        "sort_order",
        "display_role",
        "created_at",
    }
    _UPDATE_FIELDS: set[str] = {
        "field_name",
        "field_key",
        "field_type",
        "sort_order",
        "display_role",
    }

    def __init__(self, db_manager=None):
        super().__init__(db_manager)

    # ==================== 删除方法 ====================

    def delete_by_type_id(self, type_id: str) -> bool:
        """
        按 type_id 批量删除字段记录（级联清理用）

        走 _generic_batch_delete 通道：custom_record_fields 是 SYNC_TABLES 中的
        TEXT 主键表，墓碑 record_id = id。实现方式：先查 type_id 对应的 id 列表，
        再走 _generic_batch_delete（批量写墓碑+DELETE 同事务）。

        供 CustomRecordRepository.delete_type 调用。

        Args:
            type_id: 类型 ID

        Returns:
            True（无字段时也返回 True）
        """
        try:
            # 先查该类型的所有 field id 列表
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    f"SELECT {self._PRIMARY_KEY} FROM {self._TABLE_NAME} WHERE type_id = ?",
                    (type_id,),
                )
                field_ids = [row[0] for row in cursor.fetchall()]

            if not field_ids:
                return True

            # 批量删除+写墓碑（_generic_batch_delete 自带事务）
            self._generic_batch_delete(field_ids)
            return True
        except DataAccessError:
            raise
        except sqlite3.Error as e:
            logger.error("按类型ID删除字段失败: type_id=%s, error=%s", type_id, e)
            raise DataAccessError(f"按类型ID删除字段失败: {e}") from e
