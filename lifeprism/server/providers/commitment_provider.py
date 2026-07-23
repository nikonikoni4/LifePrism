"""
此文件已废弃 - CommitmentProvider 已迁移到 lifeprism.repository.providers.commitment_provider

迁移依据：.scratch/deletion-sync-02-code/issues/03-commitment-provider-migration.md

新位置：lifeprism/repository/providers/commitment_provider.py
迁移内容：
- CommitmentProvider 类（继承 LWBaseDataProvider）
- 完整子类元数据（_TABLE_NAME, _PRIMARY_KEY, _UPDATE_FIELDS, _ON_CONFLICT）
- create_commitment 走 _generic_insert
- update_commitment 走 _generic_update
- delete_commitment 走 _generic_delete（含写墓碑）
- get_commitments / get_commitment_by_id / get_commitments_by_value 直接 SQL（保持原 LEFT JOIN 行为）
- 新增 delete_by_value_id / null_value_id / count_by_value 级联方法（供 ValueProvider 使用）
- 异常处理抛出 DataAccessError（而非静默返回 None/False/[]）

为兼容遗留引用，从此处转发到新位置：
"""

# 保留转发以避免任何遗漏的引用导致 ImportError
from lifeprism.repository.providers.commitment_provider import (  # noqa: F401
    CommitmentProvider,
    commitment_provider,
)
