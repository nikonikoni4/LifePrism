"""
此文件已废弃 - JournalProvider 已迁移到 lifeprism.repository.providers.journal_provider

迁移依据：.scratch/deletion-sync-02-code/issues/02-journal-provider-migration.md

新位置：lifeprism/repository/providers/journal_provider.py
迁移内容：
- JournalProvider 类（继承 LWBaseDataProvider）
- 完整子类元数据（_TABLE_NAME, _PRIMARY_KEY, _FILTER_FIELDS, _UPDATE_FIELDS, _ON_CONFLICT）
- create_journal 走 _generic_insert
- update_journal 走 _generic_update
- delete_journal 走 _generic_delete（含写墓碑）
- get_journals_by_goal / get_journal_by_id 直接 SQL（保持原 ORDER BY 行为）
- 异常处理改为抛出 DataAccessError（而非静默返回 None/False/[]）

为兼容遗留引用，从此处转发到新位置：
"""

# 保留转发以避免任何遗漏的引用导致 ImportError
from lifeprism.repository.providers.journal_provider import (  # noqa: F401
    JournalProvider,
    journal_provider,
)
