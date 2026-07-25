# 删除端点墓碑写入端到端测试报告

**报告时间**: 2026-07-24
**测试范围**: 全项目所有删除端点（HTTP DELETE 端点 + Provider 删除方法 + 隐蔽删除逻辑）
**依据 PRD**: [.scratch/deletion-sync-02-code/prd.md](../../../.scratch/deletion-sync-02-code/prd.md)
**依据 ADR**: [2026-07-22-deletion-sync-tombstone.md](../../adr/2026-07-22-deletion-sync-tombstone.md)

## 一、背景与目标

PRD2（deletion-sync-02-code）完成了删除同步的代码改造，要求所有 `SYNC_TABLES` 的删除操作必须走 `_generic_delete` / `_generic_batch_delete` 通道，以自动写入墓碑到 `deletion_log` 表。本次测试的目标是：

1. 全面审计项目所有删除端点和删除逻辑（包括隐蔽删除）
2. 验证所有 SYNC_TABLES 的删除方法能正确写入墓碑
3. 发现并记录未走墓碑通道的删除逻辑（设计性或缺陷性）

## 二、审计方法

采用"多 agent 并行查找 + 交叉验证"的方法，共派出 5 个 subagent：

| Agent | 查找范围 | 发现数 |
|-------|---------|--------|
| Agent 1 | HTTP DELETE 端点（lifeprism/server/api/） | 31 个端点 |
| Agent 2 | Provider 层删除方法（repository/providers/ + server/providers/） | 46 个方法 |
| Agent 3 | Service/Aggregator 隐蔽删除逻辑 | 52 处 |
| Agent 4 | 同步层/LLM 工具/迁移脚本/特殊路径 | 27 处 |
| Agent 5 | 交叉验证遗漏检查 | 8 项补充 |

## 三、审计结果汇总

### 3.1 HTTP DELETE 端点（31 个）

| 类别 | 数量 | 说明 |
|------|------|------|
| 走 _generic_delete（写墓碑） | 21 个 | 含 5 个 _generic_batch_delete |
| 自定义 SQL + 显式写墓碑 | 1 个 | custom-records entries（动态表） |
| 文件系统删除（不涉及 DB） | 4 个 | add_on、chatbot、diary template、settings |
| 逻辑删除（UPDATE，不写墓碑） | 1 个 | todos/{todo_id}/waid |
| 不写墓碑（表不同步） | 3 个 | report daily/weekly/monthly |
| DROP TABLE（DDL，不写墓碑） | 1 个 | custom-records types（动态表） |

### 3.2 SYNC_TABLES 覆盖（29 张表）

| 状态 | 数量表 | 说明 |
|------|--------|------|
| 有删除方法且写墓碑 | 24 张 | 走 _generic_* 通道 |
| 仅有 schema 无 CRUD | 2 张 | daily_focus、weekly_focus |
| 仅有软删除无硬删除 | 1 张 | category_map_cache（UPDATE state=0） |
| 仅有 upsert 无删除 | 1 张 | wechat_account_state |
| 删除方法为死代码 | 1 张 | diary（DiaryProvider.delete_diary 从未被调用） |

### 3.3 隐蔽删除逻辑（按危险程度排序）

#### ★★★ 最高危
- `sync_cloud_api.sync_full_clear`：全量清空云端所有同步数据 + 文件（首次同步前调用，不写墓碑）

#### ★★ 高危（同步触发）
- `plandoc_sync_service.sync_plan_doc`：MD 同步时检测关联 todo 被删，自动级联删除 todo_list（写墓碑）
- `sync_client._pull_deletion_log`：每次同步时云端新墓碑触发本地 DELETE（不写墓碑，墓碑已存在）
- `sync_cloud_api.sync_push_deletion_log`：本地推送墓碑时云端执行 DELETE（不写墓碑，墓碑已存在）

#### ★ 中危（操作触发的隐蔽删除）
- `category_service._disable_category_map_records_*`：禁用分类时软删除 map_cache（state=0，不写墓碑）
- `category_service._enable_category_map_records_*`：启用分类时删除冲突记录（写墓碑）
- `habit_service.delete_habit` 中 challenges cancel：UPDATE 不写墓碑
- `ScreenshotCleanupWorker`：后台定时清理截图（表不同步，不写墓碑）
- `statistical_data_providers.py`：已废弃的直接 DELETE（DEPRECATED，存在误用风险）

## 四、测试实施

### 4.1 测试文件

**新增文件**: [test_delete_endpoints_tombstone_e2e.py](../../../test/core/unit/storage/test_delete_endpoints_tombstone_e2e.py)

### 4.2 测试覆盖（24 个测试用例）

| 类型 | 测试数 | 覆盖方法 |
|------|--------|---------|
| TEXT 主键表单条删除 | 14 | mood_entry/type, diary, todo, goal, journal, category/sub, value, commitment, map_cache×2, tokens_usage |
| AUTOINCREMENT 表单条删除 | 4 | mood_impact(mi-), being(tp-), being复合键, computer_usage(awbl-) |
| 批量删除 | 4 | commitment.delete_by_value_id, computer_usage.batch_delete, 边界用例×2 |
| 动态表显式写墓碑 | 2 | custom_record_aggregator.delete_entry |
| 不写墓碑验证 | 1 | commitment.null_value_id（逻辑删除） |

### 4.3 测试验证项

每个测试验证以下内容：
- 删除前记录存在
- 调用 delete 方法返回正确值
- 删除后记录消失
- deletion_log 表中有对应墓碑
- 墓碑的 target_table 正确
- 墓碑的 record_id 正确（TEXT 主键表=主键值，AUTOINCREMENT 表=hash_id）
- 墓碑的 source = "local"

## 五、测试结果

### 5.1 新增测试结果

```
============================= 24 passed in 1.22s ==============================
```

所有 24 个测试全部通过，无需修复。

### 5.2 完整墓碑测试套件结果

包含 L1-L4 + 新 E2E + 基类 + Provider 测试：

```
============================= 150 passed in 8.24s =============================
```

| 测试文件 | 测试数 | 状态 |
|---------|--------|------|
| test_l1_remaining_delete_tombstone.py | 5 | ✓ |
| test_l2_batch_delete_tombstone.py | 8 | ✓ |
| test_l3_cascade_delete_tombstone.py | 5 | ✓ |
| test_l3_custom_record_cascade_tombstone.py | 4 | ✓ |
| test_l4_category_service_delete_sink.py | 4 | ✓ |
| test_delete_endpoints_tombstone_e2e.py | 24 | ✓ |
| test_base_provider_generic_methods.py | 78 | ✓ |
| test_deletion_log_provider.py | 22 | ✓ |
| **合计** | **150** | **全部通过** |

## 六、关键发现

### 6.1 墓碑机制完整性确认

- `_generic_delete` 正确实现墓碑写入：调用 `_resolve_tombstone_record_id` + `_write_tombstone`，与 DELETE 同事务
- `_generic_batch_delete` 正确实现批量墓碑：1 次 `executemany` 墓碑 INSERT + 1 次 DELETE，同事务
- AUTOINCREMENT 表（HASH_ID_PREFIXES 中）墓碑 record_id 使用 hash_id（跨端稳定标识）
- TEXT 主键表墓碑 record_id 使用主键值
- 冲突处理：`INSERT OR IGNORE`，重复删除保留旧墓碑

### 6.2 设计性"不写墓碑"（非缺陷）

以下方法不写墓碑属于设计意图：

| 方法 | 原因 |
|------|------|
| `CommitmentProvider.null_value_id` | UPDATE 置空外键，非真删 |
| `GoalProvider.delete_goal` 中 todo_list 的 UPDATE | 仅置空 link_to_goal_id，非删除 |
| `DeletionLogProvider.cleanup_before` | 清理墓碑表自身 |
| `SyncRepository.delete_all_rows` | full_clear 场景，按 PRD2 不写墓碑 |
| `execute_tombstone_delete_with_cursor` | 墓碑已存在，避免循环触发同步 |
| `ScreenCaptureProvider.delete_screen_capture` | 表不同步 |
| `FileSyncStateProvider.delete_state` | 同步基础设施表 |
| report_provider 的 3 个删除 | daily/weekly/monthly_report 表不同步 |

### 6.3 已知限制

| 限制 | 说明 | 文档 |
|------|------|------|
| habit_chains/habit_chain_nodes 不写墓碑 | chain_id 外键引用未解决，临时移出 SYNC_TABLES | [habit-chain-tables-not-synced.md](../../known-limitations/habit-chain-tables-not-synced.md) |
| DiaryProvider.delete_diary 死代码 | 方法存在但从未被调用，diary 表无法通过 API 删除 | 本次发现 |
| category_map_cache 仅软删除 | 表在 SYNC_TABLES 中但无硬删除方法 | PRD2 确认 |
| 文件同步不删除文件 | _sync_files_full_flow 仅 PULL/PUSH/CONFLICT/SKIP | [file-deletion-not-synced.md](../../known-limitations/file-deletion-not-synced.md) |

### 6.4 潜在风险点

1. **statistical_data_providers.py 遗留代码**：仍包含直接 DELETE，虽已废弃但有误用风险，建议完成基线测试迁移后删除整个文件
2. **category_service 软删除未走墓碑**：`_disable_category_map_records_*` 的 UPDATE state=0 不写墓碑，云端无法感知
3. **habit_service.delete_habit 中 challenges cancel**：状态改为 cancelled 是 UPDATE，不写墓碑，云端无法感知
4. **DiaryProvider.delete_diary 死代码**：diary 在 SYNC_TABLES 中但实际不会产生 diary 的删除墓碑

## 七、建议

### 7.1 短期
- 删除 `lifeprism/server/providers/statistical_data_providers.py` 遗留代码，避免误用
- 为 `DiaryProvider.delete_diary` 暴露 API 端点或明确移除该方法

### 7.2 中期
- 评估 `category_service._disable_category_map_records_*` 软删除是否需要走墓碑
- 评估 `habit_service.delete_habit` 中 challenges cancel 是否需要走墓碑

### 7.3 长期（预防性）
- 建立删除端点墓碑写入的自动化检查规则（见 [tombstone-prevention-rules.md](../coding-rules/tombstone-prevention-rules.md)）
- 新增 SYNC_TABLES 时强制检查是否有删除方法且走墓碑通道
- CI 中加入墓碑测试覆盖检查

## 八、相关文档

- [PRD2: deletion-sync-02-code](../../../.scratch/deletion-sync-02-code/prd.md)
- [ADR: deletion-sync-tombstone](../../adr/2026-07-22-deletion-sync-tombstone.md)
- [ADR: deletion-log-table](../../adr/2026-07-22-deletion-log-table.md)
- [ADR: hash-id-sync-only-identifier](../../adr/2026-07-22-hash-id-sync-only-identifier.md)
- [规则: 同步友好建表规则](../../coding-rules/sync-friendly-table-design.md)
- [规则: 墓碑预防性规则](../../coding-rules/tombstone-prevention-rules.md)
- [已知限制: habit-chain-tables-not-synced](../../known-limitations/habit-chain-tables-not-synced.md)
- [已知限制: file-deletion-not-synced](../../known-limitations/file-deletion-not-synced.md)
- [测试文件: test_delete_endpoints_tombstone_e2e.py](../../../test/core/unit/storage/test_delete_endpoints_tombstone_e2e.py)
