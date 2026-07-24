---
title: 边界场景 + 表类型覆盖 + 文档
created_at: 2026-07-23
status: ready-for-agent
---

## Parent

`.scratch/deletion-sync-03-tombstone/prd.md`（同步删除 - 阶段 3：墓碑同步流程）

## What to build

覆盖 PRD 3 的边界场景和表类型验证，完成文档验收标准。本 slice 主要是扩展 S2 端到端测试覆盖不同表类型和边界场景，并撰写相关文档。

**表类型覆盖**（依据 PRD "User Stories > 边界场景"）：

1. **AUTOINCREMENT 表（hash_id）删除同步**：
   - A 设备删除 AUTOINCREMENT 表记录（墓碑 `record_id` 使用 `hash_id`）→ 同步 → B 设备记录消失
   - 涉及表：`user_app_behavior_log`、`timeline_custom_block`、`time_paradoxes`、`mood_impacts` 等（在 `HASH_ID_PREFIXES` 中的表）
   - `SyncRepository.execute_tombstone_delete` 通过 `HASH_ID_PREFIXES.get(target_table)` 判断用 `WHERE hash_id = ?`

2. **级联删除同步**：
   - A 设备删除 habit → Service 层级联删除 habit_challenges + habit_checkins → 同步 → B 设备三张表对应记录都消失
   - 验证级联删除的三张表都写了墓碑，且墓碑都传播到对端

3. **动态表（custom_*）删除同步**（C4 修复）：
   - A 设备删除 `custom_*` 动态表记录 → 同步 → B 设备记录消失
   - **实现方式**：修改 `custom_record_aggregator.delete_entry`，在 DELETE 之前调用 `deletion_log_provider.write_tombstone_with_cursor(cursor, data_table, entry_id, source="local")` 写墓碑（与 DELETE 在同一事务）
   - 动态表墓碑 `record_id` 用动态表的主键（TEXT `id`），`target_table` 用动态表名 `custom_{slug}`
   - `SyncRepository.execute_tombstone_delete` 对动态表：`HASH_ID_PREFIXES.get(target_table)` 返回 None（动态表不在 `HASH_ID_PREFIXES` 中），走 `WHERE {get_primary_key_field(target_table)} = ?` 分支
   - 动态表 schema 不在 `TABLE_CONFIGS`，但 `get_primary_key_field` 默认返回 `"id"`，可正确处理

**边界场景**（依据 PRD "User Stories > 边界场景"）：

4. **重置同步进度后墓碑仍工作**（m2 修正）：
   - 重置 `last_sync_time`（`POST /api/sync/reset-sync-progress`）后，墓碑机制仍正常工作
   - 重置只清 `last_sync_time`，不清 `deletion_log` 表
   - 重置后下次同步会拉取所有 `created_at > ""`（空字符串）的墓碑（即本地剩余未清理的墓碑）

5. **全量首同步不传播墓碑**：
   - 首次同步（`_full_sync_to_cloud`）时不传播墓碑
   - 首同步假设云端为空，不需要墓碑

6. **多表批量删除同步**：
   - 同时删除多张表的记录 → 同步 → 所有删除都传播

7. **删除-更新冲突（已知限制）反向测试**（C3/Minor-3 补充）：
   - A 删除 R → B 更新 R（`updated_at` 更晚）→ 同步 → A 拉回 R（删除被更新覆盖）
   - 验证这是 PRD US23 已知限制的预期行为，不是 bug
   - 在 known-limitations 文档中引用此测试

**文档验收**（依据 PRD "验收标准 > 文档验收"）：

**前置要求**（m4）：编写文档前阅读 `docs/docs-rules/index.md` 和 `docs/docs-rules/docs-write-rules.md`

8. **写 ADR**：`docs/adr/2026-07-22-deletion-sync-tombstone.md`
   - 删除同步墓碑机制决策
   - 含两节点假设、墓碑清理策略、`updated_at` LWW（墓碑不修改，`created_at == updated_at`，行为等价）、Pull/Push 顺序
   - 记录 `deletion_log` 从 `SYNC_TABLES` 移除的决策（走专用通道）
   - 记录新增 3 个专用端点的决策

9. **更新 PRD**（M1/Major-4 同步修改）：
   - PRD US16：改为"墓碑比较使用 `updated_at` 字段作 LWW——墓碑不修改，插入时 `created_at == updated_at`，行为等价"
   - PRD"墓碑 LWW 比较"章节：同步更新描述
   - PRD"决策汇总"表"冲突策略"行：更新为"墓碑 `updated_at` 作 LWW（等价于 `created_at`，因墓碑不修改）"
   - PRD"模块改造清单"：更新 `sync_cloud_api.py` 改造内容为"新增 3 个专用端点"
   - PRD"Implementation Decisions"中 `deletion_log` 从 `SYNC_TABLES` 移除的说明

10. **更新 spec**：`docs/specs/2026-07-16-data-sync-core-spec.md`
    - 新增"墓碑同步流程"章节
    - 描述 Pull/Push/清理三个阶段的流程（含专用端点）

11. **更新 known-limitations**：
    - 文件删除不同步（文件操作不走 LifePrism 同步管控）
    - 删除-更新冲突不自动处理（已知限制，引用反向测试）
    - 删除-重建冲突（A 删 R → 墓碑传播 → A 再创建新 R → 墓碑仍存在 → 同步时对端可能因墓碑再次删除新 R）

12. **更新 history-bugs**：`docs/history-bugs/2026-07-16-database-delete-not-synced.md`
    - 标记为已修复（引用 PRD 1+2+3 的 commit）

**S2 测试**（依据 PRD "Testing Decisions > S2"）：

位置：`test/core/integration/sync/test_sync_deletion.py`（扩展）

测试场景：
- AUTOINCREMENT 表删除同步
- 级联删除同步（habit + challenges + checkins）
- 动态表删除同步（custom_*，验证 `delete_entry` 写墓碑）
- 重置同步进度后墓碑仍工作
- 全量首同步不传播墓碑
- 多表批量删除同步
- 删除-更新冲突反向测试（已知限制预期行为）

## Acceptance criteria

### 表类型覆盖
- [ ] 端到端测试：AUTOINCREMENT 表（hash_id）删除同步传播
- [ ] 端到端测试：级联删除同步传播所有级联表（habit + challenges + checkins）
- [ ] 端到端测试：动态表（custom_*）删除同步传播
- [ ] 修改 `custom_record_aggregator.delete_entry`：通过 `write_tombstone_with_cursor` 写墓碑（与 DELETE 同事务，符合 Repository Pattern）
- [ ] `SyncRepository.execute_tombstone_delete` 对动态表正确判断（不在 `HASH_ID_PREFIXES`，走主键分支）

### 边界场景
- [ ] 端到端测试：重置 `last_sync_time` 后墓碑仍工作
- [ ] 端到端测试：全量首同步不传播墓碑
- [ ] 端到端测试：多表批量删除同步
- [ ] 端到端测试：删除-更新冲突反向测试（A 删除 → B 更新 → A 拉回，验证已知限制预期行为）

### 文档
- [ ] 编写文档前已阅读 `docs/docs-rules/index.md` 和 `docs/docs-rules/docs-write-rules.md`
- [ ] 写 ADR `docs/adr/2026-07-22-deletion-sync-tombstone.md`（含两节点假设、清理策略、`updated_at` LWW、Pull/Push 顺序、专用端点、`deletion_log` 从 SYNC_TABLES 移除）
- [ ] 更新 PRD（US16/LWW 章节/决策汇总表/模块改造清单/SYNC_TABLES 说明）
- [ ] 更新 `docs/specs/2026-07-16-data-sync-core-spec.md`（墓碑同步流程章节）
- [ ] 更新 `docs/known-limitations/`（文件删除不同步、删除-更新冲突、删除-重建冲突）
- [ ] 更新 `docs/history-bugs/2026-07-16-database-delete-not-synced.md`（标记为已修复）

## Blocked by

- `.scratch/deletion-sync-03-tombstone/issues/03-cleanup-lww-failure.md`（墓碑清理 + LWW + 失败处理）
