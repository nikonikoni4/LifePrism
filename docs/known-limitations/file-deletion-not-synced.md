---
version: 1.0
created_at: 2026-07-23
updated_at: 2026-07-23
last_updated: 创建文档初稿，记录文件删除不走墓碑同步的限制
abstract: LifePrism 同步系统只对数据库记录实现墓碑同步（删除传播），文件删除通过 file_sync_state 表的 LWW 机制处理。两端文件状态不一致时可能出现"幽灵文件"（已删文件被对端拉回）。
---

# 文件删除不走墓碑同步

## 版本

| 版本 | 更新内容 |
| ---- | -------- |
| 1.0 | 创建文档初稿 |

## 问题描述

LifePrism 同步系统覆盖两类数据：

1. **数据库记录**：29 张静态表 + 动态表 + `deletion_log` 墓碑表
2. **文件**：`SYNC_DIRECTORIES` 白名单目录（`session/`、`diary/`、`agent/`、`user/`）

墓碑同步机制（`/pull-deletion-log`、`/push-deletion-log`、`/cleanup-deletion-log`）只覆盖数据库记录的删除传播，**不覆盖文件删除**。文件删除依赖 `file_sync_state` 表的 LWW 机制：

- 文件 A 端删除 → `file_sync_state` 表中记录变为"已删除"状态
- B 端 Pull 时检测到 A 端文件状态为"已删除" → 本地也删除
- 但若 B 端在 Pull 前修改了同一路径的文件（mtime 更新），LWW 比较可能让 B 端版本覆盖 A 端的删除意图

## 影响范围

- **状态**: `acknowledged`（已确认，按当前使用场景不修复）
- **严重程度**: 低（文件删除场景少，且 `file_sync_state` 的 LWW 通常能正确处理）
- **影响范围**: `SYNC_DIRECTORIES` 白名单目录中的文件删除
- **不影响**: 数据库记录的删除（已通过墓碑同步正确处理）

## 当前假设

- **前提 1**: 文件删除场景少（用户主要修改文件，少删除）
- **前提 2**: `file_sync_state` 表的 LWW 机制能处理大部分文件删除场景（A 删除 + B 未改 → B 端正确删除）
- **前提 3**: 文件同步采用 per-file version tracking（parent_hash + current_hash + 11 状态决策矩阵），相比纯 LWW mtime 比较更精确
- **前提 4**: 云端 agent_only 不启动 dreaming，文件修改只来自会话处理，删除-修改并发概率低

## 触发条件

需要解决此限制的条件（满足以下任一时）：

1. 出现真实的"幽灵文件"问题（已删文件被对端拉回）
2. 文件删除-修改并发频率显著提升
3. 用户反馈"明明删除了却回来了"

## 临时方案

接受现状，作为已知限制文档化。出现冲突时依赖：

1. **数据备份**：每日 03:00 全量备份（见 `docs/specs/2026-07-17-data-backup-spec.md`），可从备份恢复
2. **手工删除**：用户察觉后手动删除"幽灵文件"
3. **三阶段协议兜底**：文件同步的 verify 阶段会检测两端状态不一致，触发冲突解决（diff3 + LLM 合并）

## 解决方案（未来）

若需要解决此限制，候选方案：

1. **方案 A：文件墓碑表**：新增 `file_deletion_log` 表记录文件删除意图，跨端传播删除
2. **方案 B：扩展 `file_sync_state`**：在 `file_sync_state` 表中新增 `deleted` 字段，标记删除意图
3. **方案 C：统一墓碑表**：扩展 `deletion_log` 表的 `target_table` 字段支持文件路径（如 `file:diary/2026-07-23.md`）

当前文件删除场景少，三个方案均属于过度设计，暂不实施。

## 相关文档

- Spec: [2026-07-16-data-sync-files-spec.md](../specs/2026-07-16-data-sync-files-spec.md) — 文件同步规格（per-file version tracking、三阶段协议）
- Spec: [2026-07-16-data-sync-core-spec.md](../specs/2026-07-16-data-sync-core-spec.md) — 墓碑同步机制章节（仅覆盖数据库记录）
- ADR: [2026-07-22-deletion-sync-tombstone.md](../adr/2026-07-22-deletion-sync-tombstone.md) — 墓碑同步流程架构决策
- ADR: [2026-07-14-file-sync-conflict-resolution.md](../adr/2026-07-14-file-sync-conflict-resolution.md) — 文件同步冲突解决（per-file version tracking）
- 代码: `lifeprism/sync/sync_client.py:407` — `_cleanup_deletion_log` 仅清理数据库墓碑
- 代码: `lifeprism/sync/constants.py` — `SYNC_DIRECTORIES` 白名单

## 注意事项

1. **不要在 `_pull_deletion_log` / `_push_deletion_log` 中处理文件删除**：墓碑同步流程只覆盖数据库记录，文件删除走独立的文件同步流程
2. **不要为 `file_sync_state` 表写墓碑**：`file_sync_state` 是同步元数据表，不是业务数据表，其删除由 LWW 机制处理
3. **测试覆盖**：`test/core/integration/sync/test_sync_deletion.py` 只测试数据库记录的删除传播，不覆盖文件删除（属于已知限制）
4. **文件冲突解决**：文件同步已有独立的冲突解决机制（diff3 + LLM 合并，见 ADR [2026-07-17-conflict-resolution-diff3-replaces-llm.md](../adr/2026-07-17-conflict-resolution-diff3-replaces-llm.md)），与墓碑同步机制独立
