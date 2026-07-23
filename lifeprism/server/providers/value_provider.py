"""
ValueProvider 转发 shim

本文件已迁移到 lifeprism/repository/providers/value_provider.py。
此 shim 仅为兼容旧导入路径（lifeprism.server.providers.value_provider）保留，
新代码应直接从 lifeprism.repository.providers.value_provider 导入。

迁移要点（Slice 05）：
- create_value 走 _generic_insert(data, id_prefix="val-")
- update_value 走 _generic_update(value_id, data)（修复时间戳不一致）
- delete_value 走 _generic_delete(value_id)（含写墓碑，单表删除不含级联）
- 级联协调上移到 value_service.delete_value
- count_commitments_by_value 已迁移到 CommitmentProvider.count_by_value
"""

from lifeprism.repository.providers.value_provider import ValueProvider, value_provider

__all__ = ["ValueProvider", "value_provider"]
