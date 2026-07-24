# Code Review Report

**审查范围**: `cd62d359..HEAD` + working tree (deletion sync stage2: slice01~slice10)
**审查时间**: 2026-07-23
**变更文件**: 20 个源代码文件 + 13 个测试文件 (37 files, +7730/-1369 lines)

## 架构上下文

### 相关 ADR
- [2026-07-22-deletion-log-table.md](../adr/2026-07-22-deletion-log-table.md) — 墓碑表 schema 决策 (accepted)
  - 字段名 `target_table`（非 `table_name`），`update_at: True`，LWW 用 `updated_at`
- [2026-07-22-add-hash-id-to-autoincrement-tables.md](../adr/2026-07-22-add-hash-id-to-autoincrement-tables.md) — 6 张 AUTOINCREMENT 表加 hash_id (accepted)
- [2026-07-09-lww-conflict-resolution.md](../adr/2026-07-09-lww-conflict-resolution.md) — LWW 冲突解决策略 (accepted)

### 相关 Spec
- `docs/specs/2026-07-06-repository-core-spec.md` — LWBaseDataProvider 元数据驱动 CRUD
- `docs/specs/2026-07-16-data-sync-core-spec.md` — 30 张静态表增量同步 + LWW
- `docs/specs/custom-records-module.md` — 自定义记录模块（动态表 + meta 表）

### 相关编码规则
- `docs/coding-rules/repository-module-rules.md` — 三层架构、导入纪律、Aggregator 组合模式
- `docs/coding-rules/backend-core-rules.md` — 日志规范、数据库操作规范
- `lifeprism/CLAUDE.md` — 错误处理分层规则、类型注解规范

### 决策覆盖
- 4/4 commits 有 PRD 关联
- 变更严格遵循 PRD `.scratch/deletion-sync-02-code/prd.md` 的 12 步实施顺序
- 级联删除事务原子性在 PRD Out of Scope 中明确标记为"暂不处理"

## 审查结果

Found 4 issues:

### Issue 1: `delete_computer_usage` 绕过 `_generic_delete`，不写墓碑
- **类型**: Correctness / PRD Compliance
- **置信度**: 95
- **位置**: `lifeprism/repository/providers/computer_usage_provider.py:166`
- **详情**: `delete_computer_usage` 调用 `self.db.delete(self._TABLE_NAME, where={"id": record_id})`，绕过 `_generic_delete` 通道。`user_app_behavior_log` 是 SYNC_TABLE 且是 AUTOINCREMENT 表（前缀 `awbl-`），删除时不会写墓碑到 `deletion_log`。这是 31 张 SYNC_TABLES 中唯一未被迁移的删除方法。
- **依据**: PRD Story 58 明确要求 `computer_usage_provider.delete_computer_usage` 改用 `_generic_delete`。PRD 核心约束："所有 SYNC_TABLES 的删除必须经过 `_generic_delete`"
- **触发场景**: 用户在设备 A 删除一条 computer_usage 记录 → 同步到设备 B 时该记录不会被删除（无墓碑）
- **备注**: PRD 将其归入 P5 (StatisticalDataProviders 迁移)，P5 尚未开始

### Issue 2: `update_computer_usage` 绕过 `_generic_update`，`updated_at` 不自动更新
- **类型**: Correctness / LWW Sync
- **置信度**: 90
- **位置**: `lifeprism/repository/providers/computer_usage_provider.py` (update_computer_usage 方法)
- **详情**: `update_computer_usage` 调用 `self.db.update(...)` 而非 `_generic_update`。`_generic_update` 会自动更新 `updated_at` 字段（触发 LWW 同步），而 `self.db.update()` 不会。这导致 `user_app_behavior_log` 表的更新操作不会触发 LWW 同步到其他设备。
- **依据**: PRD Story 12："`_generic_update` 不涉及 hash_id 生成，但必须走 `_generic_update` 以保证 `updated_at` 自动更新（触发 LWW 同步）"
- **触发场景**: 在设备 A 更新一条 computer_usage 记录 → `updated_at` 不变 → 同步时 LWW 比较认为该记录无变化 → 设备 B 收不到更新

### Issue 3: 5 个 Service 文件直接从 `lifeprism.repository.providers` 导入，违反导入纪律
- **类型**: Architecture / Import Discipline
- **置信度**: 85
- **位置**:
  - `lifeprism/server/services/value_service.py:17`
  - `lifeprism/server/services/commitment_service.py:8`
  - `lifeprism/server/services/goal_service.py:12`
  - `lifeprism/server/services/journal_service.py:9`
  - `lifeprism/server/services/being_service.py:10`
- **详情**: 这些 Service 文件从 `lifeprism.repository.providers.xxx` 直接导入 Provider 单例，违反了 `repository-module-rules.md` Section 2.2 的导入纪律。规则要求外部调用方只能从 `lifeprism.repository` 导入。根因是迁移后的 Provider（being_provider, commitment_provider, value_provider, journal_provider）未在 `lifeprism/repository/__init__.py` 中注册导出。
- **依据**: `docs/coding-rules/repository-module-rules.md` Section 2.2："外部调用方只能从 `lifeprism.repository` 导入，禁止直接从 `lifeprism.repository.providers` 导入"
- **触发场景**: 未来重构 repository 内部 Provider 结构时，所有直接穿透导入的 Service 文件都需要级联修改

### Issue 4: `being_provider.upsert` 使用非原子 read-then-write 模式，存在竞态条件
- **类型**: Correctness / Race Condition
- **置信度**: 80
- **位置**: `lifeprism/repository/providers/being_provider.py:387` (upsert 方法)
- **详情**: 新 upsert 先查询 `get_by_user_mode_version` 再决定 update 或 create。两个并发调用可能同时看到记录不存在，同时走 INSERT 路径，第二个 INSERT 因 `UNIQUE(user_id, mode, version)` 冲突抛出 IntegrityError。旧实现使用 `self.db.upsert` 是单条 SQL 原子操作。docstring 解释了不能用 `self.db.upsert` 的原因（hash_id 不可变），但未提及竞态风险，也未提供重试或冲突处理机制。
- **依据**: PRD Story 32："`upsert` 保留 `self.db.upsert(...)`（基类无 `_generic_upsert`）"——但新实现改为 read-then-write
- **触发场景**: 两个并发请求同时 upsert 相同的 `(user_id=1, mode='past', version=3)`，都查到记录不存在，都调用 `create()`。第二个 create 的 `_generic_insert` 触发 UNIQUE 约束冲突

## 变更摘要

### 已提交变更 (cd62d359..HEAD, 4 commits)

| Slice | 内容 | 文件数 |
|-------|------|--------|
| slice01 | 基类改造：`_generic_delete` 写墓碑 + `_generic_batch_delete` | 基类文件 |
| slice02-05 | P1-P4 Provider 迁移：Journal → Commitment → Being → Value | 4 new + 4 reduced |
| slice07-08 | L1+L2 删除通道统一：单条 + 批量删除 | 11 modified |
| slice06+09+10 | L3 级联删除 + L4 Service 下沉 + 审计 | 5 modified |

### 未提交变更 (working tree)

| 文件 | 变更 |
|------|------|
| `custom_record_aggregator.py` | `delete_type` 从原始 SQL DELETE 改为走 Provider `_generic_*` 通道（L3 级联删除） |
| `habit_providers.py` | `delete_habit` 增加级联删除 challenges + checkins（L3 级联删除） |
| `test_l3_custom_record_cascade_tombstone.py` | 新增：Custom Record 级联删除墓碑测试 (291 lines) |

### 测试覆盖

新增 13 个测试文件，覆盖：
- P1-P4 Provider 迁移等价性测试 (8 files)
- L1 单条删除墓碑测试 (1 file)
- L2 批量删除墓碑测试 (1 file)
- L3 级联删除墓碑测试 (2 files, 含未提交)
- L4 Service 下沉测试 (1 file)

### 正面发现

1. **所有已迁移文件的原始 SQL DELETE 已清零** — grep 验证 `lifeprism/repository/providers/` 下无残留 `DELETE FROM` SYNC_TABLES 原生 SQL
2. **墓碑 record_id 解析正确** — TEXT 主键表用主键值，AUTOINCREMENT 表正确解析为 hash_id
3. **批量删除模式一致** — 所有 `delete_by_*` 方法正确遵循"先查 ID 列表 → `_generic_batch_delete`"模式
4. **`_generic_batch_delete` 正确处理空列表** — 提前返回 0
5. **基类墓碑写入原子性** — `INSERT OR IGNORE` + `DELETE` 在同一事务，`get_connection` 上下文管理器统一回滚
6. **Working tree 修复及时** — 未提交的 `custom_record_aggregator.py` 和 `habit_providers.py` 修复了 committed 版本的 L3 级联删除缺失问题