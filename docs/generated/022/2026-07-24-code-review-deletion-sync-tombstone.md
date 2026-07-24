# Code Review Report

**审查范围**: commit `99872455` — `feat: deletion sync stage3 tombstone sync flow + 3 dedicated endpoints`
**审查时间**: 2026-07-24
**变更文件**: 45 个文件 (+3952 / -214)

## 架构上下文

### 相关 ADR
- [2026-07-22-deletion-sync-tombstone.md](../adr/2026-07-22-deletion-sync-tombstone.md) — 墓碑同步流程架构决策 (decided)
- [2026-07-22-deletion-log-table.md](../adr/2026-07-22-deletion-log-table.md) — 墓碑表 schema 决策 (partially-superseded)
- [2026-07-22-add-hash-id-to-autoincrement-tables.md](../adr/2026-07-22-add-hash-id-to-autoincrement-tables.md) — hash_id 字段决策 (decided)

### 相关 Spec
- [2026-07-16-data-sync-core-spec.md](../specs/2026-07-16-data-sync-core-spec.md) — 数据同步核心规格 (draft v2.1)

### 决策覆盖
- 5/5 ADR 决策有对应实现，2 个决策存在实现偏差

## 审查结果

Found 9 issues:

### Issue 1: AUTOINCREMENT 同步表缺少 hash_id 导致墓碑跨端删除目标错误

- **类型**: Architecture / Data Integrity
- **置信度**: 90
- **位置**: `lifeprism/sync/sync_repository.py:570-577`；`lifeprism/sync/constants.py:25-77`
- **详情**: `execute_tombstone_delete_with_cursor()` 通过 `HASH_ID_PREFIXES` 判断用 `hash_id` 列还是主键列。`daily_focus`、`weekly_focus`、`category_map_cache` 三张表是 AUTOINCREMENT 同步表（在 `SYNC_TABLES` 中），但**不在 `HASH_ID_PREFIXES` 中**。当墓碑同步时，这些表会 fallback 到整数主键 `id`，而 `id` 在两端的值不同，导致墓碑可能删除错误记录或无法删除目标记录。
- **依据**: [sync-friendly-table-design.md](../../coding-rules/sync-friendly-table-design.md) 规则 2——"同步表使用 AUTOINCREMENT 时必须完成全部配套，包括注册 hash_id 前缀"；ADR [2026-07-22-add-hash-id-to-autoincrement-tables.md](../adr/2026-07-22-add-hash-id-to-autoincrement-tables.md) 明确要求所有 AUTOINCREMENT 同步表需要 hash_id。
- **建议**: 为 `daily_focus`、`weekly_focus`、`category_map_cache` 三张表补充 `hash_id` 字段并在 `HASH_ID_PREFIXES` 中注册，或在本 ADR 中明确记录这些表不支持墓碑删除同步（作为已知限制）。

### Issue 2: 动态表名白名单校验过于宽松，可构造 SQL 注入

- **类型**: Security
- **置信度**: 90
- **位置**: `lifeprism/repository/sync_repository.py:_validate_table_name()`（动态表分支）；`lifeprism/repository/sync_repository.py:569-578`
- **详情**: `_validate_table_name()` 对动态表的校验仅检查 `table_name.startswith("custom_") and table_name not in TABLE_CONFIGS`，允许任何以 `custom_` 开头的字符串通过。恶意构造的 `target_table`（如 `custom_notes WHERE ? OR 1=1 -- `）会被直接拼接到 `DELETE FROM {target_table}` SQL 中，导致删除整表数据。攻击者可通过恶意同步服务器或控制云端 `deletion_log` 数据来触发。
- **依据**: OWASP SQL Injection Prevention；`_validate_table_name()` 对动态表的宽松校验是已知事实，但墓碑 DELETE 路径是该表名首次被用于破坏性操作（之前仅用于建表 DDL）。
- **建议**: 对动态表名增加正则校验 `^custom_[a-z][a-z0-9_]*$`，并验证表名对应 `custom_record_types` 中已注册的 slug。

### Issue 3: `_pull_deletion_log` 非 SQLite 异常导致事务未回滚

- **类型**: Architecture / Correctness
- **置信度**: 85
- **位置**: `lifeprism/sync/sync_client.py:331-363`
- **详情**: `_pull_deletion_log` 的事务回滚依赖 `DatabaseManager.get_connection()` 上下文管理器，但该管理器仅 catch `sqlite3.Error` 执行 rollback。若循环中出现 `KeyError`（云端返回的墓碑缺少字段）、`DataAccessError` 或其他非 SQLite 异常，事务不会回滚，连接带着未提交的事务返回连接池。日志消息"事务已回滚"与实际情况不符。
- **依据**: ADR Decision 2——"DELETE 和墓碑写入必须在同一事务，失败则整个事务回滚"；当前实现仅在 `sqlite3.Error` 时满足此保证。
- **建议**: 在 `_pull_deletion_log` 的事务块中显式 `try/except BaseException`，调用 `conn.rollback()` 后 re-raise；或修改 `DatabaseManager.get_connection()` 使其对所有异常执行 rollback。

### Issue 4: 专用墓碑通道未强制隔离——`deletion_log` 仍可通过通用同步通道传播

- **类型**: Architecture
- **置信度**: 85
- **位置**: `lifeprism/sync/sync_client.py:sync_once()`；`lifeprism/server/api/sync_cloud_api.py:sync_pull/sync_push`
- **详情**: 虽然 `deletion_log` 已从默认 `SYNC_TABLES` 移除，但 `sync_once(tables=...)` 接受调用方传入的 tables 参数且不做过滤，`/pull` 和 `/push` 端点也不拒绝 `deletion_log` 表名。若调用方传入 `tables=["deletion_log"]`，墓碑会同时走专用通道和通用数据同步通道，完全恢复 ADR 决策 1 要避免的"双重同步 + LWW 语义不匹配"问题。
- **依据**: ADR Decision 1——"deletion_log 不在 SYNC_TABLES 中，仅通过专用端点同步"
- **建议**: 在 `sync_once` 和 `/pull`/`/push` 端点中显式过滤或拒绝 `deletion_log` 表名，防止其进入通用数据同步通道。

### Issue 5: 模块文档字符串声称"LWW 用 updated_at 比较"与 ADR 决策和实现不符

- **类型**: Documentation / Code Comment
- **置信度**: 85
- **位置**: `lifeprism/repository/providers/deletion_log_provider.py:4`；`lifeprism/sync/sync_client.py:288-289`；`lifeprism/server/api/sync_cloud_api.py:343`
- **详情**: 多处代码注释声称墓碑同步使用 "LWW 检查" 或 "LWW 用 updated_at 比较"，但 ADR Decision 3 明确选择了 `INSERT OR IGNORE`（存在性检查）而非 `updated_at` 比较，实际代码也使用 `INSERT OR IGNORE`。注释与实际行为和 ADR 均不一致，会误导后续维护者。
- **依据**: ADR [2026-07-22-deletion-sync-tombstone.md](../adr/2026-07-22-deletion-sync-tombstone.md) Decision 3——"方案 A：本地已有墓碑则 INSERT OR IGNORE 跳过"
- **建议**: 将模块文档字符串和所有相关注释中的 "LWW" 改为 "墓碑存在性检查（INSERT OR IGNORE）"或等效表述。

### Issue 6: API 端点使用 `except Exception` 违反项目 API 层规则

- **类型**: Code Quality
- **置信度**: 85
- **位置**: `lifeprism/server/api/sync_cloud_api.py:389`
- **详情**: `sync_push_deletion_log` 端点使用 `except Exception` 捕获所有异常。项目 API 层规则要求"API 层不使用 try/except，异常自然冒泡到全局异常处理器"。虽然此处 re-raise 了异常，但 `except Exception` 过于宽泛，可能掩盖非预期的系统异常（如 `KeyboardInterrupt`、`SystemExit`）。
- **依据**: 项目 `backend-api-rules.md`——"API 层不使用 try/except"
- **建议**: 将 `except Exception` 替换为 `except (sqlite3.Error, DataAccessError)` 或移除 try/except 让异常自然冒泡。

### Issue 7: 新增墓碑端点缺少 Pydantic 请求/响应模型

- **类型**: Best Practices
- **置信度**: 80
- **位置**: `lifeprism/server/api/sync_cloud_api.py:359-365`（`tombstones: list[dict[str, Any]]`）
- **详情**: 三个新端点使用 `dict[str, Any]` 作为请求/响应类型，缺少 Pydantic 模型验证。`tombstones` 列表中的每条记录应有 `target_table`、`record_id`、`created_at` 等必填字段，但这些字段的存在性和类型未经 FastAPI 自动校验。缺失字段会导致 `KeyError`（500 错误），而非 422 参数校验错误。
- **依据**: FastAPI 最佳实践；项目 `backend-api-rules.md`——"请求体使用 Pydantic 模型"
- **建议**: 定义 `TombstoneItem`、`SyncPullDeletionLogResponse`、`SyncPushDeletionLogResponse` 等 Pydantic 模型，使用 `response_model` 参数。

### Issue 8: `DeletionLogProvider` 三个写入方法存在大量重复代码

- **类型**: Code Quality
- **置信度**: 80
- **位置**: `lifeprism/repository/providers/deletion_log_provider.py:57-234`
- **详情**: `create_tombstone`（line 57）、`write_tombstone_with_cursor`（line 111）、`create_tombstone_with_cursor`（line 189）三个方法重复了相同的 source 校验逻辑（3 次完全相同）、相同的 UUID 生成逻辑、相同的 `INSERT OR IGNORE` SQL。`write_tombstone_with_cursor` 和 `create_tombstone_with_cursor` 的核心逻辑几乎完全一致，仅 `source` 默认值和 `created_at` 参数不同。
- **依据**: DRY 原则；重复代码增加维护成本，修改校验逻辑需要同步三处。
- **建议**: 提取 `_validate_source(source)` 辅助方法；让 `write_tombstone_with_cursor` 委托给 `create_tombstone_with_cursor`。

### Issue 9: 缺少云侧端点集成测试、Push 失败路径测试和 cursor 变体方法单元测试

- **类型**: Testing
- **置信度**: 80
- **位置**: `test/core/integration/sync/test_sync_deletion.py`；`test/core/unit/storage/test_deletion_log_provider.py`
- **详情**: 
  1. 三个新云侧端点（`/pull-deletion-log`、`/push-deletion-log`、`/cleanup-deletion-log`）仅通过 mock 测试，没有使用 `TestClient` 的集成测试
  2. `_push_deletion_log` HTTP 失败路径无测试覆盖（US18 仅测试了 Pull 失败）
  3. `get_tombstone_with_cursor` 和 `create_tombstone_with_cursor` 两个关键方法无单元测试
  4. 级联删除测试直接调用 Repository 方法而非真实 Service 层路径
- **依据**: PRD 验收标准 US18——"墓碑同步失败时整个 sync_once 必须失败"；PRD S1 测试范围——"DeletionLogProvider CRUD"
- **建议**: 补充云侧端点 `TestClient` 集成测试、Push 失败路径测试、cursor 变体方法单元测试、Service 层级联删除测试。

## 变更摘要

本次提交实现了删除同步 Stage 3（墓碑同步流程），包含 5 个核心变更：

1. **新 Provider**：`DeletionLogProvider`（420 行），提供墓碑表的 CRUD + 增量查询 + cursor 变体方法
2. **新端点**：`/pull-deletion-log`、`/push-deletion-log`、`/cleanup-deletion-log` 三个专用端点，替代 `SYNC_TABLES` 通道
3. **sync_once 集成**：`SyncClient` 新增 `_pull_deletion_log`、`_push_deletion_log`、`_cleanup_deletion_log`，流程顺序为墓碑 Pull → 数据 Pull → 墓碑 Push → 数据 Push → 文件 → 清理 → 更新 last_sync_time
4. **Aggregator 适配**：`CustomRecordRepository` 内部实例化 `DeletionLogProvider`，动态表删除走墓碑同步
5. **测试**：新增 16 个端到端测试 + 40+ Provider 单元测试

### 优秀实践

- ADR 文档结构清晰，5 个决策均包含方案对比、决策逻辑表和演进历史
- Spec 文档准确反映了实现，`key_function` 行号与实际代码一致
- 已知限制文档详尽描述了 3 个边界场景（删除-更新冲突、删除-重建冲突、文件删除）
- 测试覆盖 16 个 PRD 场景，Fixture 清理完善，避免交叉污染
- SQL 值均使用参数化查询（`?` 占位符），遵循防注入最佳实践
- 所有端点正确使用 `Depends(verify_sync_api_key)` 认证
- Repository 层导入纪律遵守良好，外部调用方统一从 `lifeprism.repository` 导入