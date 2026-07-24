---
version: 1.0
created_at: 2026-07-23
updated_at: 2026-07-23
last_updated: 创建文档初稿，记录墓碑同步不解决删除-更新冲突的限制
abstract: A 端删除记录后写墓碑，B 端若同时更新该记录（upsert 写回），B 端的更新会覆盖 A 端的删除意图，导致记录"复活"。墓碑同步流程不自动处理此冲突，作为已知限制接受。
---

# 删除-更新冲突不解决

## 版本

| 版本 | 更新内容 |
| ---- | -------- |
| 1.0 | 创建文档初稿 |

## 问题描述

在严格两节点（本地↔云端）的主备模式下，理论上同一时间只有一端 Agent 在工作，但实际场景中仍可能出现删除-更新并发冲突：

1. A 端删除记录 R → 写入 `deletion_log` 墓碑（`source=local`，`created_at = T1`）
2. 在 A 端推送墓碑到云端之前，B 端通过数据 Pull 收到云端缓存的 R 旧版本（云端尚未物理删除）
3. B 端基于 R 旧版本做更新（`updated_at = T2 > T1`），upsert 写回云端
4. A 端推送墓碑到云端 → 云端执行 DELETE → B 端的更新被删除
5. **或**：A 端推送墓碑晚于 B 端推送更新 → 云端先 upsert 更新 → 后执行 DELETE → 最终记录被删除，B 端更新丢失

墓碑同步流程**不比较** `updated_at`，只用 `INSERT OR IGNORE` 跳过已存在的墓碑。因此无法检测"对端是否有更新的版本"，也无法回滚已执行的 DELETE。

## 影响范围

- **状态**: `acknowledged`（已确认，按当前使用场景不修复）
- **严重程度**: 低（主备模式下冲突概率 < 0.1%）
- **影响范围**: 所有同步表的删除-更新并发场景
- **不影响**: 正常的删除-删除场景（两端都删除同一记录，结果一致）

## 当前假设

- **前提 1**: 主备模式下，同一时间只有一端的 Agent 在工作（本地在线时云端跳过消息处理），删除-更新并发概率极低
- **前提 2**: 墓碑不更新，`updated_at == created_at`，比较 `updated_at` 无实际意义
- **前提 3**: 项目当前无 CRDT 或版本号字段支持冲突检测

## 触发条件

需要解决此冲突的条件（满足以下任一时）：

1. 出现真实的删除-更新冲突导致用户可见的数据丢失
2. 项目从主备模式转向多客户端并发模式
3. 用户反馈"明明更新了却消失了"

## 临时方案

接受现状，作为已知限制文档化。出现冲突时依赖：

1. **数据备份**：每日 03:00 全量备份（见 `docs/specs/2026-07-17-data-backup-spec.md`），可从备份恢复
2. **手工修复**：用户察觉后重新创建记录
3. **监控**：通过 `/api/sync/status` 查询 `deletion_log` 行数异常增长

## 解决方案（未来）

若需要解决此冲突，候选方案：

1. **方案 A：墓碑版本号**：墓碑新增 `version` 字段，与业务表的 `updated_at` 比较，墓碑版本较低时跳过 DELETE
2. **方案 B：CRDT**：转向 CRDT（Conflict-free Replicated Data Type），自然处理删除-更新冲突
3. **方案 C：应用层仲裁**：删除前查询对端是否有更新，有则提示用户选择

当前主备模式下冲突概率极低，三个方案均属于过度设计，暂不实施。

## 相关文档

- ADR: [2026-07-22-deletion-sync-tombstone.md](../adr/2026-07-22-deletion-sync-tombstone.md) — 决策 3 LWW 简化为 `INSERT OR IGNORE` 跳过
- ADR: [2026-07-09-lww-conflict-resolution.md](../adr/2026-07-09-lww-conflict-resolution.md) — LWW 冲突解决策略
- Spec: [2026-07-16-data-sync-core-spec.md](../specs/2026-07-16-data-sync-core-spec.md) — 墓碑同步机制章节
- 代码: `lifeprism/sync/sync_client.py:287` — `_pull_deletion_log` 中 LWW 检查逻辑
- 代码: `lifeprism/server/api/sync_cloud_api.py:339` — `/push-deletion-log` 端点 LWW 检查逻辑

## 注意事项

1. **不要为墓碑表新增 `version` 字段**：在主备模式下属于过度设计，且会破坏 `INSERT OR IGNORE` 跳过的简洁实现
2. **不要在墓碑 Pull/Push 时比较 `updated_at`**：墓碑不更新，比较无意义
3. **测试覆盖**：`test/core/integration/sync/test_sync_deletion.py` 中已包含两端同时删除的场景，但未覆盖删除-更新并发场景（属于已知限制）
