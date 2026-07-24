---
version: 1.0
created_at: 2026-07-23
updated_at: 2026-07-23
last_updated: 创建文档初稿，记录删除-重建冲突时墓碑跳过新记录的限制
abstract: A 端删除记录 R 后写墓碑，B 端在收到墓碑前重建了同 ID 的新记录 R'，A 端墓碑 Pull 到 B 端后会因 UNIQUE 约束 INSERT OR IGNORE 跳过，导致 R' 在 A 端被错误删除而墓碑副本未写入。
---

# 删除-重建冲突时墓碑跳过新记录

## 版本

| 版本 | 更新内容 |
| ---- | -------- |
| 1.0 | 创建文档初稿 |

## 问题描述

墓碑同步使用 `UNIQUE(target_table, record_id)` 约束 + `INSERT OR IGNORE` 跳过已存在的墓碑。这在"两端同时删除同一记录"场景下工作正常，但在"一端删除-另一端重建"场景下会导致数据丢失：

1. A 端删除记录 R（`record_id = X`）→ 写入 `deletion_log` 墓碑（`target_table = T, record_id = X, source = local, created_at = T1`）
2. 在 A 端推送墓碑到云端之前，B 端重建同 ID 的新记录 R'（`record_id = X`，但内容不同，`updated_at = T2 > T1`）
3. A 端推送墓碑到云端 → 云端 `execute_tombstone_delete` 执行 `DELETE FROM T WHERE id = X` → **R' 被错误删除**
4. 云端尝试写墓碑副本 → 因 `UNIQUE(target_table, record_id)` 约束 + `INSERT OR IGNORE` → **跳过写入**（云端已有 A 端推送的墓碑）

更严重的是反向场景：

5. A 端的墓碑 Pull 到 B 端 → B 端执行 `DELETE FROM T WHERE id = X` → **R' 被错误删除**
6. A 端墓碑副本写入 → 因 `UNIQUE` 约束跳过（A 端已有原墓碑）

**根本原因**：墓碑的 LWW 简化为 `INSERT OR IGNORE`，不比较 `updated_at`，无法识别"对端有更新的版本"。墓碑一旦写入，对端任何同 ID 的新记录都会被 DELETE 覆盖。

## 影响范围

- **状态**: `acknowledged`（已确认，按当前使用场景不修复）
- **严重程度**: 中（出现概率中等，但发生时数据丢失严重）
- **影响范围**: 所有同步表的"删除-重建"冲突场景
- **不影响**: 正常的删除-删除场景（结果都是删除，无差异）

## 当前假设

- **前提 1**: 主备模式下，同一时间只有一端的 Agent 在工作，删除-重建并发概率低
- **前提 2**: 用户通常不会"删除后立即重建同一 ID"，重建时倾向于使用新 ID
- **前提 3**: TEXT 主键表的 ID 由用户/AI 显式指定，冲突概率比 AUTOINCREMENT 表低
- **前提 4**: AUTOINCREMENT 表的 `hash_id` 是新生成的 UUID，重建时几乎不会冲突

## 触发条件

需要解决此冲突的条件（满足以下任一时）：

1. 出现真实的删除-重建冲突导致用户可见的数据丢失
2. 业务流程中有"删除-重建"的高频操作（如重置 habit、重新创建同 slug 类型）
3. 用户反馈"明明重建了却消失了"

## 临时方案

接受现状，作为已知限制文档化。出现冲突时依赖：

1. **数据备份**：每日 03:00 全量备份（见 `docs/specs/2026-07-17-data-backup-spec.md`），可从备份恢复
2. **新 ID 重建**：建议用户重建时使用新 ID，避免与已删记录冲突
3. **AI 工具提示**：在 AI 工具创建记录时检查 `deletion_log` 是否有同 ID 墓碑，有则提示用户

## 解决方案（未来）

若需要解决此冲突，候选方案：

1. **方案 A：墓碑版本号**：墓碑新增 `version` 字段（取自被删记录的 `updated_at`），Pull 时比较业务表当前记录的 `updated_at` 与墓碑的 `version`，业务表更新则跳过 DELETE
2. **方案 B：墓碑 TTL**：墓碑写入时设置过期时间（如 24 小时），过期后不再生效，允许重建
3. **方案 C：CRDT**：转向 CRDT，自然处理删除-重建冲突

当前主备模式下冲突概率低，三个方案均属于过度设计，暂不实施。

## 相关文档

- ADR: [2026-07-22-deletion-sync-tombstone.md](../adr/2026-07-22-deletion-sync-tombstone.md) — 决策 3 LWW 简化为 `INSERT OR IGNORE` 跳过
- ADR: [2026-07-22-deletion-log-table.md](../adr/2026-07-22-deletion-log-table.md) — `UNIQUE(target_table, record_id)` 约束定义
- Spec: [2026-07-16-data-sync-core-spec.md](../specs/2026-07-16-data-sync-core-spec.md) — 墓碑同步机制章节
- 代码: `lifeprism/repository/providers/deletion_log_provider.py:189` — `create_tombstone_with_cursor` 使用 `INSERT OR IGNORE`
- 代码: `lifeprism/repository/sync_repository.py:543` — `execute_tombstone_delete_with_cursor` 执行 DELETE

## 注意事项

1. **不要为墓碑表新增 `version` 字段**：在主备模式下属于过度设计，且会破坏 `INSERT OR IGNORE` 跳过的简洁实现
2. **不要移除 `UNIQUE(target_table, record_id)` 约束**：该约束是 `INSERT OR IGNORE` 跳过的前提，移除会导致重复墓碑
3. **测试覆盖**：`test/core/integration/sync/test_sync_deletion.py` 已包含两端同时删除的场景（测试场景 6），但未覆盖删除-重建并发场景（属于已知限制）
4. **AI 工具建议**：未来可在 LLM 工具创建记录时增加 `deletion_log` 检查，提示用户该 ID 曾被删除
