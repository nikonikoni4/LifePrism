---
title: DeletionLogProvider 基础设施 + S1 单元测试
created_at: 2026-07-23
status: ready-for-agent
---

## Parent

`.scratch/deletion-sync-03-tombstone/prd.md`（同步删除 - 阶段 3：墓碑同步流程）

## What to build

新建 `DeletionLogProvider`（继承 `LWBaseDataProvider`），为 `deletion_log` 墓碑表提供 CRUD + 增量查询 + source 过滤 + 清理能力。这是 PRD 3 的基础设施层，为后续 sync_once 集成墓碑 Pull/Push/清理做准备。

**DeletionLogProvider 元数据**（依据 PRD "Implementation Decisions > DeletionLogProvider 元数据"）：

```python
_TABLE_NAME = "deletion_log"
_PRIMARY_KEY = "id"
_ON_CONFLICT = "ignore"  # 与 _write_tombstone 的 INSERT OR IGNORE 语义一致（M2）
_FILTER_FIELDS = {"source", "target_table"}
_ORDER_FIELDS = {"created_at"}
_SELECT_FIELDS = {"id", "target_table", "record_id", "source", "created_at", "updated_at"}
```

**需实现的方法**：

1. **写入墓碑**：`create_tombstone(target_table, record_id, source, created_at=None)` — `id` 用 `dl-` 前缀 + 8 位 hex（通过 `_generic_insert(id_prefix='dl-')` 生成）。`created_at` 为 None 时用 `get_utc_now_iso()` 生成当前时间；否则用传入值（用于 Pull/Push 写副本时保留原墓碑时间戳，保持两端时间戳一致）。`created_at` 传入时，`updated_at` 同步设为同一值（保持墓碑"不修改"语义，LWW 比较正确）
2. **增量查询**：`get_tombstones_since(last_sync_time, source=None)` — 按 `created_at > last_sync_time` 查询，可选按 `source` 过滤
3. **清理**：`cleanup_before(last_sync_time)` — 清理 `created_at <= last_sync_time` 的记录
4. **按 target_table + record_id 查询**：`get_tombstone(target_table, record_id)` — 用于 LWW 比较（判断两端是否有同一墓碑）
5. **在同一事务内写墓碑**：`write_tombstone_with_cursor(cursor, target_table, record_id, source="local")` — 接受外部 cursor 参数，在同一事务内写墓碑。供 Aggregator（如 `CustomRecordAggregator.delete_entry`）调用以保证事务边界。SQL 封装在此方法中（INSERT OR IGNORE INTO deletion_log），符合 Repository Pattern（C4）

**`_write_tombstone` 与 `create_tombstone` 的关系**（m1）：
- `_write_tombstone`（基类方法）保持现状：source 硬编码 "local"，仅用于本地删除时写 source=local 墓碑（通过 `_generic_delete` 内部调用）
- `create_tombstone`（DeletionLogProvider 领域方法）支持任意 source 和可选 `created_at`，用于 Pull/Push 写副本
- 两者独立，不强制重构 `_write_tombstone`

**`source` 字段约束**（m5）：
- DB 层无 CHECK 约束（schema 只有 NOT NULL）
- 由 `create_tombstone` 和 `write_tombstone_with_cursor` 方法在 Provider 层校验 `source in ('local', 'cloud')`，非法值抛 ValueError

**注册单例**：在 `lifeprism/repository/providers/__init__.py` 注册 `deletion_log_provider` 单例，在 `lifeprism/repository/__init__.py` 添加 `deletion_log_repository` 别名导出。

**S1 单元测试**（依据 PRD "Testing Decisions > S1"）：

位置：`test/core/unit/storage/test_deletion_log_provider.py`

测试内容：
- 写入墓碑（`target_table` / `record_id` / `source` / `created_at`）
- 按 `created_at > last_sync_time` 增量查询
- 按 `source` 过滤（local/cloud）
- 清理 `created_at <= last_sync_time`
- 字段约束验证（`target_table` 非空、`record_id` 非空、`source` 只能是 local/cloud）
- `id` 前缀 `dl-` 验证
- 按 `target_table + record_id` 查询

Prior art：`test/core/unit/storage/test_wechat_account_state_provider.py`

## Acceptance criteria

- [ ] `DeletionLogProvider` 新建并继承 `LWBaseDataProvider`，元数据符合 PRD 定义（`_ON_CONFLICT = "ignore"`）
- [ ] `create_tombstone(target_table, record_id, source, created_at=None)` 方法实现，`id` 用 `dl-` 前缀 + 8 位 hex；`created_at` 传入时 `updated_at` 同步设为同一值
- [ ] `write_tombstone_with_cursor(cursor, target_table, record_id, source="local")` 方法实现，接受外部 cursor 保证同一事务（供 Aggregator 调用）
- [ ] `get_tombstones_since` 方法实现，支持 `created_at > last_sync_time` 增量查询 + 可选 `source` 过滤
- [ ] `cleanup_before` 方法实现，清理 `created_at <= last_sync_time` 的记录
- [ ] `get_tombstone` 方法实现，按 `target_table + record_id` 查询
- [ ] `source` 字段在 Provider 层校验 `source in ('local', 'cloud')`，非法值抛 ValueError
- [ ] `deletion_log_provider` 单例在 `providers/__init__.py` 注册
- [ ] `deletion_log_repository` 别名在 `repository/__init__.py` 导出
- [ ] S1 单元测试全部通过（覆盖 CRUD + 增量查询 + source 过滤 + 清理 + 字段约束 + `write_tombstone_with_cursor`）
- [ ] 外部调用方从 `lifeprism.repository` 导入（导入纪律）

## Blocked by

None - can start immediately
