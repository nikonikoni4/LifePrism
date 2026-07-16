# 数据库物理删除无法传播到同步对端

## 元信息

- **发生时间**: 2026-07-16（同步系统设计初期已存在）
- **发现时间**: 2026-07-16
- **修复状态**: ⏳ 待修复
- **影响范围**: 全部数据库同步表（mood_entries、habits、goals、diary、todo_list、custom_* 等 40+ 张表）
- **bug 类型**: 设计缺陷 — 增量同步方案遗漏了 DELETE 操作的传播
- **严重程度**: 高（P1）— 导致两端数据一致性被悄然破坏，用户无法察觉

## 触发规则

在以下场景时阅读此文档：
- 排查"删了一条记录，同步后又出现了"的问题
- 讨论同步系统中 DELETE 操作的传播机制
- 设计 tombstone / 软删除 / 删除日志表等方案
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

等待讨论并确定方案。

## 复用场景

- 任何同步系统的设计 — 增量同步方案必须为 DELETE 操作预留传播通道
- Repository 层设计 — 物理删除前需评估同步/审计/回滚等需求
