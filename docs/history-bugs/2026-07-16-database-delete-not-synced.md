# 数据库物理删除无法传播到同步对端

## 元信息

- **发生时间**: 2026-07-16（同步系统设计初期已存在）
- **发现时间**: 2026-07-16
- **修复状态**: ✅ 已修复（2026-07-23，PRD 1/2/3 全部完成，墓碑同步机制落地）
- **影响范围**: 全部数据库同步表（mood_entries、habits、goals、diary、todo_list、custom_* 等 40+ 张表）
- **bug 类型**: 设计缺陷 — 增量同步方案遗漏了 DELETE 操作的传播
- **严重程度**: 高（P1）— 导致两端数据一致性被悄然破坏，用户无法察觉
- **修复方案**: Tombstone 表方案（新增 `deletion_log` 表记录删除意图，通过 3 个专用端点跨端传播 DELETE）
- **关联 PRD**: deletion-sync-01-schema（Schema 变更）+ deletion-sync-02a-statistical（代码适配）+ deletion-sync-03-tombstone（墓碑同步流程）
- **关联 ADR**: [2026-07-22-deletion-log-table.md](../adr/2026-07-22-deletion-log-table.md) + [2026-07-22-deletion-sync-tombstone.md](../adr/2026-07-22-deletion-sync-tombstone.md) + [2026-07-22-add-hash-id-to-autoincrement-tables.md](../adr/2026-07-22-add-hash-id-to-autoincrement-tables.md)

## 触发规则

在以下场景时阅读此文档：
- 排查"删了一条记录，同步后又出现了"的问题（**已在 PRD 3 修复，新版无此问题**）
- 讨论同步系统中 DELETE 操作的传播机制
- 设计 tombstone / 软删除 / 删除日志表等方案（参考本 bug 的修复方案）
- 排查云端和本地数据不一致但无错误日志的情况
- 修改 Repository 层的 delete 方法或同步 push/pull 逻辑

## Bug 简述

所有数据库表（mood_entries、habits、goals、diary、todo_list、custom_* 等）的删除操作均通过 `LWBaseDataProvider._generic_delete()` 执行**物理 DELETE**（`DELETE FROM {table} WHERE {pk} = ?`），删除后没有任何痕迹残留。同步的 Push 和 Pull 两端均只做增量查询（`WHERE updated_at > last_sync_time`），只能传播 CREATE 和 UPDATE 操作。物理删除的记录不在查询结果中，删除信息永远不会传播到对端，导致被删记录在对端永久保留为"幽灵数据"。

## 复现场景

1. Endpoint A 删除记录 X（物理 DELETE FROM）
2. Endpoint A 执行 Push → `query_incremental()` 只查 `WHERE updated_at > last_sync_time`，记录 X 已不存在，不会被 Push
3. Endpoint B 执行 Pull → 服务端同样只返回增量记录，没有 X 被删的任何信息
4. **结果：记录 X 在 Endpoint B 上永久保留，两端数据分叉且无自动修复路径**

## 根因分析

同步机制是纯**增量追加式**（INSERT OR REPLACE / UPSERT only），缺少 DELETE 操作的感知和传播能力：

| 操作 | 是否能被增量查询捕获 | 是否能传播 |
|------|---------------------|-----------|
| INSERT | ✅ `updated_at` 变化 | ✅ |
| UPDATE | ✅ `updated_at` 变化 | ✅ |
| DELETE（物理） | ❌ 记录消失 | ❌ |

### 代码位置

- 删除基类：[lifeprism/repository/base_providers/lw_base_data_provider.py:1268-1304](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/repository/base_providers/lw_base_data_provider.py#L1268-L1304) — `_generic_delete()` 执行物理 DELETE
- Push 增量查询：[lifeprism/repository/sync_repository.py:223-305](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/repository/sync_repository.py#L223-L305) — `query_incremental()` 只查 `WHERE updated_at > ?`
- Pull 服务端：[lifeprism/server/api/sync_cloud_api.py:187-250](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/server/api/sync_cloud_api.py#L187-L250) — `sync_pull()` 同样只做增量查询

## 候选修复方案

| 方案 | 改动量 | 兼容性 | 风险 |
|------|--------|--------|------|
| **软删除**：各表加 `deleted_at` 列，DELETE 改为 `SET deleted_at = NOW()`，查询加 `WHERE deleted_at IS NULL` | 大（40+ 表改 DDL + 所有查询 + 所有 delete 方法） | 需迁移历史数据 | 中 — 影响面广，查询遗漏时泄露已删数据 |
| **Tombstone 表**：新增 `deleted_records` 表记录 `(table_name, pk_value, deleted_at)`，同步作为特殊"删除指令"传播 | 中（新建一张表 + 修改 `_generic_delete()` + 修改 push/pull） | 无需改已有表 | 低 — Delete 行为不变，只是多了日志写入 |
| **全量对比同步**：Pull 时对比两端主键集合，发现对端有本端无的视为"需删除" | 中（修改 sync_pull 逻辑 + 新增主键快照端点） | 无需改已有表 | 中 — 大表对比性能开销大 |

## 修复方案（已实施）

**采用方案 B：Tombstone 表方案**，分三阶段实施：

### PRD 1：Schema 变更（已完成 2026-07-22）

- 新增 `deletion_log` 墓碑表（字段：`id`/`target_table`/`record_id`/`source`/`created_at`/`updated_at`，`UNIQUE(target_table, record_id)` 约束）
- 为 6 张 AUTOINCREMENT 表新增 `hash_id TEXT NOT NULL UNIQUE` 字段作为跨端稳定标识
- 迁移脚本 `m015_add_deletion_log_table.py` 建表 + 回填 hash_id
- 详见 ADR [2026-07-22-deletion-log-table.md](../adr/2026-07-22-deletion-log-table.md) + [2026-07-22-add-hash-id-to-autoincrement-tables.md](../adr/2026-07-22-add-hash-id-to-autoincrement-tables.md)

### PRD 2：代码适配（已完成 2026-07-23）

- `_generic_delete` 内部调用 `DeletionLogProvider.write_tombstone_with_cursor` 写墓碑
- 所有 Provider 的删除通道统一走 `_generic_delete`
- `CustomRecordRepository.delete_entry` 在 DELETE 事务内写墓碑
- 详见 ADR [2026-07-22-deletion-sync-tombstone.md](../adr/2026-07-22-deletion-sync-tombstone.md) 决策 4

### PRD 3：墓碑同步流程（已完成 2026-07-23）

- 从 `SYNC_TABLES` 移除 `deletion_log`，改用 3 个专用端点（`/pull-deletion-log`、`/push-deletion-log`、`/cleanup-deletion-log`）
- HTTP 在事务外，DELETE + 墓碑写入在事务内（cursor 变体方法保证原子性）
- LWW 简化为 `INSERT OR IGNORE` 跳过（墓碑不更新，`updated_at == created_at`）
- `sync_once` 流程：墓碑 Pull → 数据 Pull → 墓碑 Push → 数据 Push → 文件 → 清理 → 更新 `last_sync_time`
- 端到端测试 16 个场景覆盖（`test/core/integration/sync/test_sync_deletion.py`）
- 详见 ADR [2026-07-22-deletion-sync-tombstone.md](../adr/2026-07-22-deletion-sync-tombstone.md)

## 已知限制（修复后仍存在）

墓碑同步方案修复了核心删除传播问题，但仍有以下已知限制（详见 `docs/known-limitations/`）：

1. **删除-更新冲突不解决**：A 删除 + B 更新同一条记录，B 端 upsert 会覆盖 A 端的删除意图 → `docs/known-limitations/delete-update-conflict-not-resolved.md`
2. **删除-重建冲突时墓碑跳过新记录**：A 删除后 B 重建同一 ID 记录，A 端墓碑会跳过 B 端的新记录 → `docs/known-limitations/delete-recreate-conflict-tombstone-skip.md`
3. **文件删除不走墓碑同步**：墓碑机制只覆盖数据库记录，文件删除走 `file_sync_state` 的 LWW → `docs/known-limitations/file-deletion-not-synced.md`

## 复用场景

- 任何同步系统的设计 — 增量同步方案必须为 DELETE 操作预留传播通道
- Repository 层设计 — 物理删除前需评估同步/审计/回滚等需求
- 墓碑表方案选型 — 专用端点 vs SYNC_TABLES 通道的取舍（参考 ADR [2026-07-22-deletion-sync-tombstone.md](../adr/2026-07-22-deletion-sync-tombstone.md) 决策 1）
