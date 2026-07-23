"""
此文件已废弃 - BeingProvider 已迁移到 lifeprism.repository.providers.being_provider

迁移依据：.scratch/deletion-sync-02-code/issues/04-being-provider-migration.md

新位置：lifeprism/repository/providers/being_provider.py
迁移内容：
- BeingProvider 类（继承 LWBaseDataProvider）
- 完整子类元数据（_TABLE_NAME, _PRIMARY_KEY, _FILTER_FIELDS, _UPDATE_FIELDS, _ON_CONFLICT）
- create 走 _generic_insert（AUTOINCREMENT 表，自动生成 tp- 前缀 hash_id）
- update 走 _generic_update(hash_id, data)
- delete 走 _generic_delete(hash_id)（含写墓碑，AUTOINCREMENT 表墓碑 record_id = hash_id）
- 复合键方法（*_by_user_mode_version）先查 hash_id 再调用 _generic_*
- upsert 改用"先查 hash_id 再 update/create"（self.db.upsert 在新 schema 下 INSERT
  路径缺 hash_id 且 UPDATE 路径会改变 hash_id，破坏同步语义）
- get_latest_version 保留原生 SQL（基类无 _generic_max）
- 异常处理抛出 DataAccessError（而非静默返回 None/False）
- 单例改用 LazySingleton

为兼容遗留引用，从此处转发到新位置：
"""

# 保留转发以避免任何遗漏的引用导致 ImportError
from lifeprism.repository.providers.being_provider import (  # noqa: F401
    BeingProvider,
    being_provider,
)
