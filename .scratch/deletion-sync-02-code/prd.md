---
title: 同步删除 - 阶段 2：代码适配（Provider 迁移 + 通道统一）
created_at: 2026-07-22
updated_at: 2026-07-22
status: ready-for-agent
type: refactor
---

# 同步删除 - 阶段 2：代码适配（Provider 迁移 + 通道统一）

## 总任务说明

本 PRD 是"数据库删除同步"任务链的**第 2 步（共 3 步）**，依赖 PRD 1（Schema 变更）完成。

```
[PRD 1] Schema 变更（已完成）
    │   6 张 AUTOINCREMENT 表加 hash_id 字段
    │   新增 deletion_log 墓碑表
    │   _generic_insert / upsert_rows_with_lww 的 hash_id 逻辑
    ▼
[PRD 2] 代码适配（本 PRD）
    │   server/providers/ 迁移到 repository/providers/
    │   所有写入通道统一走 _generic_insert
    │   所有删除通道统一走 _generic_delete（含写墓碑）
    │   LWW 去重键改用 hash_id
    ▼
[PRD 3] 墓碑同步流程
        sync_once 集成墓碑 Pull/Push/清理
        DeletionLogProvider
        端到端验证
```

**本 PRD 的边界**：让所有 Provider 的写入/删除通道统一走 `_generic_*` 方法，`_generic_delete` 内部写墓碑（写入 `deletion_log` 表），但不涉及墓碑的同步传播流程（属于 PRD 3）。

## Problem Statement

LifeWatch-AI 的 `lifeprism/server/providers/` 目录下存在 5 个遗留 Provider，它们是 repo 模块迁移时漏网的技术债。这些 Provider 虽然继承了 `LWBaseDataProvider`，但完全未使用基类提供的 `_generic_insert` / `_generic_update` / `_generic_delete` 方法，所有 CRUD 均使用原生 SQL。

同时，`repository/providers/` 下已迁移的 Provider 中，也有部分删除通道不走 `_generic_delete`（直接执行 SQL DELETE）。

这导致两个问题：
1. **写入不一致**：部分 Provider 不走 `_generic_insert`，AUTOINCREMENT 表的 `hash_id` 可能不会被正确生成。
2. **删除不一致**：部分删除通道不走 `_generic_delete`，墓碑不会被写入 `deletion_log` 表，删除同步会漏。

## Solution

### 两个核心约束（缺一不可）

本 PRD 的所有改动围绕两个核心约束，**必须同时满足**：

1. **写入通道统一（_generic_insert）**：所有 AUTOINCREMENT 表的写入必须经过 `_generic_insert`，由该方法（PRD 1 已实现）在插入时自动生成 `hash_id`。**不走此通道的写入会导致 `hash_id` 为空**，后续删除时墓碑的 `record_id` 跨端不匹配，删除同步失败。
   - **重点对象**：6 张 AUTOINCREMENT 表（PRD 1 已加 hash_id）
   - TEXT 主键表不涉及 hash_id 生成，但也应走 `_generic_insert` 保持通道统一

2. **删除通道统一（_generic_delete）**：**所有 SYNC_TABLES 的删除必须经过 `_generic_delete`（或 `_generic_batch_delete`）**，由该入口在删除前写墓碑到 `deletion_log` 表。**不走此通道的删除不会写墓碑**，删除同步会漏。
   - **重点对象**：所有 SYNC_TABLES（31 张表，含 AUTOINCREMENT 表和 TEXT 主键表），**不管批量删除还是单个删除，最终都要指向 `_generic_delete` / `_generic_batch_delete`**
   - **范围不止当前迁移的 5 个 Provider**：已迁移的 `repository/providers/` 下的 Provider、Aggregator 层、Service 层中所有对 SYNC_TABLES 的删除都要审计和统一
   - 非 SYNC_TABLES（如 `screen_captures`）不需要墓碑

### 三部分工作

1. **Provider 迁移**：5 个 server/providers/ 下的 Provider 迁移到 repository/providers/。
2. **写入通道统一**：所有 SYNC_TABLES 的 create/insert 改用 `_generic_insert`（**重点：6 张 AUTOINCREMENT 表必须走，保证 hash_id 生成**）。
3. **删除通道统一**：所有 SYNC_TABLES 的 delete 改用 `_generic_delete` / `_generic_batch_delete`（含写墓碑）。

### 迁移优先级与依赖关系

```
P1 JournalProvider（独立，goal_journal 是 TEXT 主键）
P2 CommitmentProvider（独立，commitments 是 TEXT 主键）
P3 BeingProvider（依赖 PRD 1 的 hash_id，time_paradoxes 是 AUTOINCREMENT 表）
P4 ValueProvider（依赖 P2，user_values 是 TEXT 主键，级联删除需协同 CommitmentProvider）
P5 StatisticalDataProviders（依赖 PRD 1 的 hash_id + P1-P4，单独制定详细 PRD）
```

### 写入通道统一分阶段

- **W1 server/providers/ 迁移时统一（5 个 Provider）**：P1-P4 迁移时 create 改用 `_generic_insert`（P3 BeingProvider 的 `time_paradoxes` 是 AUTOINCREMENT 表，**必须走**以保证 hash_id）
- **W2 repository/providers/ 已迁移 Provider 审计**：审计已迁移 Provider 中是否存在绕过 `_generic_insert` 的写入路径（特别是 6 张 AUTOINCREMENT 表的 Provider），发现则统一改造
- **W3 同步层 upsert 通道**：`SyncRepository.upsert_rows_with_lww` 的 hash_id 逻辑在 PRD 1 已处理，本 PRD 验证不回退

### 删除通道统一分阶段

**全局审计结果**：31 张 SYNC_TABLES 中，发现 **31 处不合规物理删除点**（原生 SQL DELETE 或 `self.db.delete()`），分布在 Provider 层、Aggregator 层、Service 层。必须全部改造。

- **L1 单表单条删除**：改用 `_generic_delete`
- **L2 批量删除**：改用 `_generic_batch_delete`（新增方法）
- **L3 复杂级联删除**：为每张子表分别写墓碑
- **L4 Service/Aggregator 层绕过 Provider 的删除**：下沉到 Provider 层调用 `_generic_*`
- **L5 非物理删除但改变同步状态的 SQL（UPDATE state=0 等）**：审计是否需要写墓碑（本次审计未发现，但需在实施时确认）

## User Stories

### 基类方法改造

1. 作为系统开发者，`_generic_delete` 内部判断 `self._TABLE_NAME in SYNC_TABLES` 时，在删除前先写墓碑到 `deletion_log` 表。
2. 作为系统开发者，`_generic_delete` 对非 SYNC_TABLES（如 `screen_captures`）不写墓碑。
3. 作为系统开发者，`_generic_delete` 对 AUTOINCREMENT 表的墓碑 `record_id` 使用 `hash_id`（前端传入自增 `id` 时，Provider 内部先查 `hash_id` 再删除）。
4. 作为系统开发者，`_generic_delete` 对 TEXT 主键表的墓碑 `record_id` 使用主键值（行为不变）。
5. 作为系统开发者，墓碑写入与删除操作在同一事务内，要么都成功要么都回滚。
6. 作为系统开发者，新增 `_generic_batch_delete(record_ids)` 方法，批量删除时为每条记录分别写墓碑，墓碑写入 + 批量 DELETE 在同一事务内。
7. 作为系统开发者，`_generic_batch_delete` 采用批量 SQL（1 次墓碑写入 + 1 次 DELETE），而非循环单条。
8. 作为系统开发者，移除 `habit_chain_nodes` 的 DB CASCADE（`ON DELETE CASCADE`），纯应用层级联，确保墓碑必写。

#### _generic_insert 的 hash_id 保障（写入通道核心约束）

9. 作为系统开发者，**所有 AUTOINCREMENT 表的写入必须经过 `_generic_insert`**，由该方法（PRD 1 已实现）自动生成 `hash_id`。
10. 作为系统开发者，`_generic_insert` 对 AUTOINCREMENT 表在插入时生成 `hash_id`（格式：`{表名前缀}-{12位hex}`），对 TEXT 主键表使用调用方传入的 ID（行为不变）。
11. 作为系统开发者，任何绕过 `_generic_insert` 直接执行 `INSERT INTO ...` 的写入路径必须改造（特别是 6 张 AUTOINCREMENT 表）。
12. 作为系统开发者，`_generic_update` 不涉及 hash_id 生成（hash_id 在插入时确定，后续不可变），但必须走 `_generic_update` 以保证 `updated_at` 自动更新（触发 LWW 同步）。

### P1：JournalProvider 迁移

9. 作为系统维护者，我希望 `JournalProvider` 从 `server/providers/` 迁移到 `repository/providers/`。
10. 作为系统开发者，迁移后定义完整子类元数据（`_TABLE_NAME = "goal_journal"`、`_PRIMARY_KEY = "id"`、`_FILTER_FIELDS`、`_UPDATE_FIELDS`、`_ON_CONFLICT`）。
11. 作为系统开发者，`create_journal` 改用 `_generic_insert(data, id_prefix="journal-")`。
12. 作为系统开发者，`update_journal` 改用 `_generic_update(journal_id, data)`。
13. 作为系统开发者，`delete_journal` 改用 `_generic_delete(journal_id)`。
14. 作为系统开发者，异常处理从"静默返回 None/False"改为"抛出 `DataAccessError`"。
15. 作为 API 用户，迁移后 `/goal/journals` 的 5 个端点必须保持原有行为不变。
16. 作为回归测试者，迁移前先补齐基线测试。

### P2：CommitmentProvider 迁移

17. 作为系统维护者，我希望 `CommitmentProvider` 从 `server/providers/` 迁移到 `repository/providers/`。
18. 作为系统开发者，迁移后定义完整子类元数据（`_TABLE_NAME = "commitments"`、`_PRIMARY_KEY = "id"`、`_UPDATE_FIELDS = {"content", "value_id", "status"}`、`_ON_CONFLICT`）。
19. 作为系统开发者，`create_commitment` 改用 `_generic_insert(data, id_prefix="cmt-")`，`status` 默认值由 service 层注入。
20. 作为系统开发者，`update_commitment` 改用 `_generic_update(commitment_id, data)`，**修复时间戳不一致**（改用 `get_utc_now_iso()`）。
21. 作为系统开发者，`delete_commitment` 改用 `_generic_delete(commitment_id)`。
22. 作为系统开发者，在 `CommitmentProvider` 新增 `delete_by_value_id(value_id) -> int`（级联删除某价值下所有承诺）。
23. 作为系统开发者，在 `CommitmentProvider` 新增 `null_value_id(value_id) -> int`（置空某价值下所有承诺的 value_id）。
24. 作为系统开发者，在 `CommitmentProvider` 新增 `count_by_value(value_id) -> int`（从 ValueProvider 迁移）。
25. 作为 API 用户，迁移后 `/commitment/` 的 5 个端点必须保持原有行为不变。

### P3：BeingProvider 迁移

26. 作为系统维护者，我希望 `BeingProvider` 从 `server/providers/` 迁移到 `repository/providers/`。
27. 作为系统开发者，修复表名常量命名：`TABLE_NAME` → `_TABLE_NAME`。
28. 作为系统开发者，定义完整子类元数据（`_TABLE_NAME = "time_paradoxes"`、`_PRIMARY_KEY = "hash_id"`（PRD 1 已加 hash_id）、`_FILTER_FIELDS = {"user_id", "mode", "version"}`、`_ON_CONFLICT = "abort"`）。
29. 作为系统开发者，`create` 改用 `_generic_insert(data)`（PRD 1 后自动生成 hash_id）。
30. 作为系统开发者，`update` / `delete` 改用 `_generic_update(hash_id, data)` / `_generic_delete(hash_id)`，前端传入自增 `id` 时先查 `hash_id`。
31. 作为系统开发者，复合键方法（`*_by_user_mode_version`）采用"先查 `hash_id` 再调用 `_generic_*`"方案。
32. 作为系统开发者，`upsert` 保留 `self.db.upsert(...)`（基类无 `_generic_upsert`）。
33. 作为系统开发者，`get_latest_version` 保留原生 SQL（基类无 `_generic_max`）。
34. 作为系统开发者，单例改用 `LazySingleton`。
35. 作为 API 用户，迁移后 `/being` 的 7 个端点必须保持原有行为不变。

### P4：ValueProvider 迁移

36. 作为系统维护者，我希望 `ValueProvider` 从 `server/providers/` 迁移到 `repository/providers/`。
37. 作为系统开发者，定义完整子类元数据（`_TABLE_NAME = "user_values"`、`_PRIMARY_KEY = "id"`、`_ON_CONFLICT = "abort"`、`_UPDATE_FIELDS = {"keywords", "content_positive", "content_negative", "sort_order"}`）。
38. 作为系统开发者，`create_value` 改用 `_generic_insert(data, id_prefix="val-")`。
39. 作为系统开发者，`update_value` 改用 `_generic_update(value_id, data)`，**修复时间戳不一致**。
40. 作为系统开发者，`delete_value_with_cascade` 重构为 `delete_value(value_id)` 调用 `_generic_delete(value_id)`，级联逻辑上移到 service 层。
41. 作为系统开发者，`count_commitments_by_value` 迁移到 `CommitmentProvider.count_by_value`。
42. 作为系统开发者，`value_service.delete_value` 重构为协调 `CommitmentProvider` + `ValueProvider`。
43. 作为 API 用户，迁移后 `/value/` 的 5 个端点必须保持原有行为不变，包括 `DELETE /value/{value_id}?cascade=True/False`。

### P5：StatisticalDataProviders 迁移（框架性描述）

44. 作为系统维护者，`StatisticalDataProviders` 迁移**详细实现单独制定 PRD**，本 PRD 仅提供框架。
45. 作为系统开发者，P5 按子任务分解：删除 4 个死代码方法 → 迁移 13 个 user_app_behavior_log 方法到 ComputerUsageProvider → 迁移 4 个 tokens_usage_log 方法到 TokensUsageProvider → 处理基类 11 个方法 → 更新 4 个 service 文件 → 删除原文件。

### 写入通道统一（_generic_insert 保障 hash_id）

> **核心约束**：6 张 AUTOINCREMENT 表的写入必须走 `_generic_insert`，否则 `hash_id` 为空，删除时墓碑 `record_id` 跨端不匹配。TEXT 主键表也应走 `_generic_insert` 保持通道统一。

**W1：server/providers/ 迁移时统一（P1-P4 已覆盖）**

- P1 `create_journal` 改用 `_generic_insert`（story 11，TEXT 主键）
- P2 `create_commitment` 改用 `_generic_insert`（story 19，TEXT 主键）
- P3 `create` 改用 `_generic_insert`（story 29，**AUTOINCREMENT 表，必须走**）
- P4 `create_value` 改用 `_generic_insert`（story 38，TEXT 主键）

**W2：repository/providers/ 已迁移 Provider 审计**

作为系统开发者，审计 `repository/providers/` 下所有 SYNC_TABLES 的 Provider，确认 create 方法是否都走 `_generic_insert`。重点关注 6 张 AUTOINCREMENT 表：

| AUTOINCREMENT 表 | 前缀 | Provider | 审计要点 |
|------------------|------|---------|---------|
| `user_app_behavior_log` | `awbl-` | `ComputerUsageProvider` | `create_computer_usage` 是否走 `_generic_insert` |
| `time_paradoxes` | `tp-` | `BeingProvider`（P3 迁移后） | `create` 是否走 `_generic_insert` |
| `habits` | `hb-` | `HabitProvider` | create 方法是否走 `_generic_insert` |
| `habit_chains` | `hc-` | `HabitChainProvider` | create 方法是否走 `_generic_insert` |
| `habit_chain_nodes` | `hcn-` | `HabitChainProvider` | create 方法是否走 `_generic_insert` |
| `habit_challenges` / `habit_checkins` | `hc-` / `hci-` | `HabitProvider` | create 方法是否走 `_generic_insert` |

审计后发现的绕过路径，必须改造为走 `_generic_insert`。

**W3：同步层 upsert 通道验证**

作为系统开发者，验证 `SyncRepository.upsert_rows_with_lww` 对 AUTOINCREMENT 表的 hash_id 处理逻辑（PRD 1 已实现）未被回退，云端同步写入的记录 hash_id 正确生成。

### 删除通道统一（L1 单表单条删除 → _generic_delete）

> **全局约束**：所有 SYNC_TABLES 的单条删除必须走 `_generic_delete`。以下 13 处为审计发现的不合规点。

46. 作为系统开发者，`commitment_provider.delete_commitment`（commitments 表）改用 `_generic_delete`。
47. 作为系统开发者，`journal_provider.delete_journal`（goal_journal 表）改用 `_generic_delete`。
48. 作为系统开发者，`statistical_data_providers.delete_event`（user_app_behavior_log 表）改用 `_generic_delete`。
49. 作为系统开发者，`value_provider.delete_value`（user_values 表）改用 `_generic_delete`。
50. 作为系统开发者，`behavior_analysis_provider.delete_*`（behavior_analysis 表）改用 `_generic_delete`。
51. 作为系统开发者，`raw_behavior_analysis_provider.delete_*`（raw_behavior_analysis 表）改用 `_generic_delete`。
52. 作为系统开发者，`plan_doc_provider.delete_plan_doc`（plan_doc 表）改用 `_generic_delete`。
53. 作为系统开发者，`todo_provider` 中所有 `DELETE FROM todo_list`（todo_list 表）改用 `_generic_delete`。
54. 作为系统开发者，`being_provider.delete_by_user_mode_version`（time_paradoxes 表）改用 `_generic_delete`（迁移后，先查 hash_id 再删除）。
55. 作为系统开发者，`being_provider.delete`（time_paradoxes 表，**原 PRD 漏列**）改用 `_generic_delete`（迁移后）。
56. 作为系统开发者，`habit_checkin_provider.delete_checkin`（habit_checkins 表，**原 PRD 漏列**）改用 `_generic_delete`（先查 id 再删除）。
57. 作为系统开发者，`custom_block_provider.delete_custom_block`（timeline_custom_block 表，**原 PRD 漏列**）改用 `_generic_delete`（当前用 `self.db.delete`）。
58. 作为系统开发者，`computer_usage_provider.delete_computer_usage`（user_app_behavior_log 表，**原 PRD 漏列**）改用 `_generic_delete`（当前用 `self.db.delete`，P5 迁移时处理）。
59. 作为系统开发者，`statistical_data_providers.delete_category_map_cache_by_id`（multi/single_purpose_map_cache 表，**原 PRD 漏列**）改用对应 Provider 的 `_generic_delete`（按前缀路由）。

### 删除通道统一（L2 批量删除 → _generic_batch_delete）

> **全局约束**：所有 SYNC_TABLES 的批量删除必须走 `_generic_batch_delete`。以下 12 处为审计发现的不合规点。

60. 作为系统开发者，`statistical_data_providers.batch_delete_events`（user_app_behavior_log 表）改用 `_generic_batch_delete`。
61. 作为系统开发者，`map_cache_providers.batch_delete_multi_purpose_map_cache` 改用 `_generic_batch_delete`。
62. 作为系统开发者，`map_cache_providers.batch_delete_single_purpose_map_cache` 改用 `_generic_batch_delete`。
63. 作为系统开发者，`statistical_data_providers.batch_delete_category_map_cache_by_ids`（multi + single 分支，**原 PRD 漏列**）改用 `_generic_batch_delete`。
64. 作为系统开发者，`category_service._enable_category_map_records_by_category`（multi 分支，**原 PRD 漏列**）改用 `_generic_batch_delete`（先查 ID 列表）。
65. 作为系统开发者，`category_service._enable_category_map_records_by_category`（single 分支，**原 PRD 漏列**）改用 `_generic_batch_delete`（先查 ID 列表）。
66. 作为系统开发者，`category_service._enable_category_map_records_by_sub_category`（multi 分支，**原 PRD 漏列**）改用 `_generic_batch_delete`（先查 ID 列表）。
67. 作为系统开发者，`category_service._enable_category_map_records_by_sub_category`（single 分支，**原 PRD 漏列**）改用 `_generic_batch_delete`（先查 ID 列表）。
68. 作为系统开发者，`todo_provider.delete_todo_cascade`（todo_list 表批量，**原 PRD 漏列**）改用 `_generic_batch_delete`。
69. 作为系统开发者，`todo_provider.batch_delete_todos`（todo_list 表批量，**原 PRD 漏列**）改用 `_generic_batch_delete`。
70. 作为系统开发者，`habit_challenge_provider.delete_by_habit_id`（habit_challenges 表级联清理，**原 PRD 漏列**）改用 `_generic_batch_delete`（先查 ID 列表）。
71. 作为系统开发者，`habit_checkin_provider.delete_by_habit_id`（habit_checkins 表级联清理，**原 PRD 漏列**）改用 `_generic_batch_delete`（先查 ID 列表）。

### 删除通道统一（L3 级联删除）

72. 作为系统开发者，`value_provider.delete_value_with_cascade` 重构后，cascade=True 时调用 `CommitmentProvider.delete_by_value_id`（内部为每条 commitment 写墓碑）。
73. 作为系统开发者，`habit_chain_providers.delete_chain` 在级联删除 `habit_chain_nodes` + `habit_chains` 时分别为两张表写墓碑。
74. 作为系统开发者，`habit_providers.delete_habit` 在级联删除 `habit_challenges` + `habit_checkins` + `habits` 时分别为三张表写墓碑。
75. 作为系统开发者，`custom_record_aggregator.delete_type` 在级联删除 `custom_record_fields` + 动态表 `custom_*` 时分别为每张表写墓碑。

### 删除通道统一（L4 Service/Aggregator 层绕过 Provider）

> **风险点**：Service 层和 Aggregator 层直接执行 DELETE SQL，绕过 Provider，无法调用 `_generic_*`。必须下沉到 Provider 层。

76. 作为系统开发者，`category_service.py` 中 4 处直接 `DELETE FROM multi/single_purpose_map_cache`（L2 已列出）下沉到对应 Provider 调用 `_generic_batch_delete`。
77. 作为系统开发者，`custom_record_aggregator.py` 中 2 处直接 `DELETE FROM custom_record_fields/custom_record_types`（L3 已列出）下沉到对应 Provider 调用 `_generic_delete` / `_generic_batch_delete`。

### 不写墓碑的特殊路径

78. 作为系统，云端 `sync_repository.full_clear`（全量清空）**不写墓碑**——非增量删除同步范围。
79. 作为系统，迁移脚本中的 DELETE **不写墓碑**——一次性操作。

## Implementation Decisions

### 基类方法改造

#### `_generic_delete` 写墓碑

```python
def _generic_delete(self, record_id: str) -> bool:
    self._validate_table_name()
    
    # 仅对 SYNC_TABLES 写墓碑
    if self._TABLE_NAME in SYNC_TABLES:
        # AUTOINCREMENT 表：record_id 应为 hash_id
        # TEXT 主键表：record_id 为主键值
        self._write_tombstone(
            target_table=self._TABLE_NAME,
            record_id=record_id,
            source="local",
        )
    
    sql = f"DELETE FROM {self._TABLE_NAME} WHERE {self._PRIMARY_KEY} = ?"
    # ... 原有删除逻辑（墓碑 + DELETE 在同一事务）
```

#### `_generic_batch_delete`

```python
def _generic_batch_delete(self, record_ids: list[str]) -> int:
    if not record_ids:
        return 0
    self._validate_table_name()
    
    with self.db.get_connection() as conn:
        try:
            # 1. 批量写墓碑（仅 SYNC_TABLES）
            if self._TABLE_NAME in SYNC_TABLES:
                tombstones = [
                    self._build_tombstone_dict(self._TABLE_NAME, rid, "local")
                    for rid in record_ids
                ]
                self._batch_insert_tombstones(conn, tombstones)
            
            # 2. 批量 DELETE
            placeholders = ", ".join(["?"] * len(record_ids))
            sql = f"DELETE FROM {self._TABLE_NAME} WHERE {self._PRIMARY_KEY} IN ({placeholders})"
            cursor = conn.cursor()
            cursor.execute(sql, record_ids)
            conn.commit()
            return cursor.rowcount
        except Exception:
            conn.rollback()
            raise
```

### P1 JournalProvider 元数据

```python
_TABLE_NAME = "goal_journal"
_PRIMARY_KEY = "id"
_DATE_FIELD = "date"
_ON_CONFLICT = "abort"
_FILTER_FIELDS = {"goal_id", "date"}
_ORDER_FIELDS = {"date", "created_at"}
_UPDATE_FIELDS = {"date", "time", "content", "mood", "duration", "tags"}
```

### P2 CommitmentProvider 元数据

```python
_TABLE_NAME = "commitments"
_PRIMARY_KEY = "id"
_ON_CONFLICT = "abort"
_FILTER_FIELDS = {"status", "value_id"}
_UPDATE_FIELDS = {"content", "value_id", "status"}
```

新增方法：`delete_by_value_id(value_id) -> int`、`null_value_id(value_id) -> int`、`count_by_value(value_id) -> int`。

### P3 BeingProvider 元数据

```python
_TABLE_NAME = "time_paradoxes"
_PRIMARY_KEY = "hash_id"  # PRD 1 已加 hash_id
_ON_CONFLICT = "abort"
_FILTER_FIELDS = {"user_id", "mode", "version"}
_ORDER_FIELDS = {"version"}
_UPDATE_FIELDS = {"content", "ai_abstract"}
```

复合键方法（`*_by_user_mode_version`）：先查 `hash_id` 再调用 `_generic_update(hash_id, data)` / `_generic_delete(hash_id)`。

### P4 ValueProvider 元数据

```python
_TABLE_NAME = "user_values"
_PRIMARY_KEY = "id"
_ON_CONFLICT = "abort"  # 防止默认 "replace" 覆盖
_UPDATE_FIELDS = {"keywords", "content_positive", "content_negative", "sort_order"}
```

级联删除重构：`delete_value_with_cascade` → `delete_value(value_id)` 调用 `_generic_delete(value_id)`，级联逻辑上移到 `value_service.delete_value`。

### DB CASCADE 移除

移除 `habit_chain_nodes` 的 `ON DELETE CASCADE`，纯应用层级联。

### 17 处删除通道改造清单

#### 通过 `_generic_delete` 删除的（L1，9 处）

详见 Further Notes 的审计结果表。

#### 不通过 `_generic_delete` 删除的（L2+L3，8 处）

详见 Further Notes 的审计结果表。

## Testing Decisions

### 测试接缝

#### S1：`_generic_delete` 拦截写墓碑

**位置**：扩展 `test/core/unit/storage/test_base_provider_generic_methods.py`

**测试内容**：
- 删除 SYNC_TABLES 记录前先写墓碑
- 删除非 SYNC_TABLES 不写墓碑
- AUTOINCREMENT 表删除时墓碑 `record_id` 为 `hash_id`
- TEXT 主键表删除时墓碑 `record_id` 为主键值
- 批量删除为每条记录分别写墓碑
- 级联删除为所有级联被删的 SYNC_TABLES 分别写墓碑
- 墓碑 + DELETE 在同一事务（失败回滚）

#### S2：P1-P4 Provider 迁移

**位置**：`test/core/unit/storage/test_journal_provider.py` 等（新增）

**测试内容**：
- 每个 Provider 的 CRUD 方法改用 `_generic_*` 后行为等价
- API 端点行为等价
- 级联删除（ValueProvider）的 cascade=True/False 两种路径

#### S3：hash_id 迁移脚本

**位置**：`test/core/unit/repository/test_migrate_hash_id.py`（PRD 1 已定义）

## Out of Scope

1. **墓碑同步流程**：sync_once 集成墓碑 Pull/Push/清理，属于 PRD 3。
2. **DeletionLogProvider**：墓碑表 Provider 的 CRUD，属于 PRD 3。
3. **StatisticalDataProviders 详细实现**：单独制定 PRD。
4. **显式事务协调机制**：P4 级联删除的事务原子性暂不处理。
5. **Aggregator 模式重构**：`goal_service._get_journals_for_goal` 的跨 Provider 调用暂保留。

## Further Notes

### 5 个 Provider 审计汇总

| Provider | 文件行数 | 方法数 | 测试覆盖 | 核心难点 |
|---------|---------|--------|---------|---------|
| P1 JournalProvider | 216 | 5 | 0% | 跨 Provider 调用 |
| P2 CommitmentProvider | 226 | 6 | 0% | 跨表操作需下沉 |
| P3 BeingProvider | 436 | 11 | 0% | 复合键 + hash_id |
| P4 ValueProvider | 204 | 6 | 0% | 级联删除协同 |
| P5 StatisticalDataProviders | 995 | 14 | ~0% | 1 类操作 6 张表 |

### 31 处删除通道审计结果（全局审计）

> 审计范围：31 张 SYNC_TABLES 的所有删除路径（排除 migrations/、server/api/、SyncRepository.full_clear）

#### 合规情况汇总

| 状态 | 表数 | 说明 |
|------|------|------|
| ✅ 完全合规 | 9 张 | 删除已走 `_generic_delete`（注：基类改造前不写墓碑，改造后自动写） |
| ⚠️ 部分合规 | 4 张 | 部分删除走，部分不走 |
| ❌ 完全不合规 | 14 张 | 所有删除都不走 `_generic_*` |
| ➖ 无删除 | 4 张 | 该表无任何删除操作 |

#### L1 单表单条删除（13 处）

| 表 | 文件位置 | 改造方式 |
|---|---------|---------|
| `commitments` | commitment_provider.py:217 | P2 迁移时改用 `_generic_delete` |
| `goal_journal` | journal_provider.py:203 | P1 迁移时改用 `_generic_delete` |
| `user_app_behavior_log` | statistical_data_providers.py:387 | P5 迁移时改用 `_generic_delete` |
| `user_app_behavior_log` | computer_usage_provider.py:166 | 改用 `_generic_delete`（当前 `self.db.delete`，P5 时处理） |
| `user_values` | value_provider.py:170 | P4 迁移时改用 `_generic_delete` |
| `behavior_analysis` | behavior_analysis_provider.py:257 | 改用 `_generic_delete` |
| `raw_behavior_analysis` | raw_behavior_analysis_provider.py:255 | 改用 `_generic_delete` |
| `plan_doc` | plan_doc_provider.py:279 | 改用 `_generic_delete` |
| `todo_list` | todo_provider.py:356, 416 | 改用 `_generic_delete`（2 处） |
| `time_paradoxes` | being_provider.py:371, 395 | P3 迁移时改用 `_generic_delete`（2 处，含 `delete` 和 `delete_by_user_mode_version`） |
| `habit_checkins` | habit_providers.py:607 | 改用 `_generic_delete`（先查 id） |
| `timeline_custom_block` | custom_block_provider.py:245 | 改用 `_generic_delete`（当前 `self.db.delete`） |
| `multi/single_purpose_map_cache` | statistical_data_providers.py:901 | 改用对应 Provider 的 `_generic_delete`（按前缀路由） |

#### L2 批量删除（12 处）

| 表 | 文件位置 | 改造方式 |
|---|---------|---------|
| `user_app_behavior_log`（批量） | statistical_data_providers.py:408 | P5 迁移时改用 `_generic_batch_delete` |
| `multi_purpose_map_cache`（批量） | map_cache_providers.py:365 | 改用 `_generic_batch_delete` |
| `single_purpose_map_cache`（批量） | map_cache_providers.py:727 | 改用 `_generic_batch_delete` |
| `multi/single_purpose_map_cache`（批量） | statistical_data_providers.py:938, 945 | 改用 `_generic_batch_delete`（2 处，按前缀分支） |
| `multi_purpose_map_cache`（条件批量） | category_service.py:1055, 1167 | 下沉到 Provider + `_generic_batch_delete`（先查 ID 列表） |
| `single_purpose_map_cache`（条件批量） | category_service.py:1093, 1201 | 下沉到 Provider + `_generic_batch_delete`（先查 ID 列表） |
| `todo_list`（批量） | todo_provider.py:356, 416 | 改用 `_generic_batch_delete`（2 处） |
| `habit_challenges`（级联清理） | habit_providers.py:479 | 改用 `_generic_batch_delete`（先查 ID 列表） |
| `habit_checkins`（级联清理） | habit_providers.py:627 | 改用 `_generic_batch_delete`（先查 ID 列表） |

#### L3 级联（4 处表组）

| 表组 | 文件位置 | 改造方式 |
|------|---------|---------|
| `user_values` + 级联 `commitments` | value_provider.py:150-170 | P4 重构为 service 层协调 |
| `habit_chains` + 级联 `habit_chain_nodes` | habit_chain_providers.py:189-190 | 级联时为每张表写墓碑 |
| `habits` + 级联 `habit_challenges` + `habit_checkins` | habit_providers.py:479, 627 | 级联时为每张表写墓碑 |
| `custom_record_types` + 级联 + 动态表 | custom_record_aggregator.py:359-361, 668 | 改用统一入口 |

#### 无删除操作的 SYNC_TABLES（4 张）

| 表 | 说明 |
|---|------|
| `daily_focus` | 仅有 schema，无任何 CRUD 代码 |
| `weekly_focus` | 仅有 schema，无任何 CRUD 代码 |
| `category_map_cache` | 废弃表，无任何 CRUD 操作 |
| `wechat_account_state` | 仅有 upsert，无删除方法 |

#### 风险提示

1. **`_generic_delete` 当前未写墓碑**：基类 `lw_base_data_provider.py:1268` 的 `_generic_delete` 仅执行 DELETE，需 PRD 2 改造为写墓碑后再执行其他迁移。
2. **`_generic_batch_delete` 尚未实现**：基类无此方法，必须先实现。
3. **Service/Aggregator 层绕过 Provider**：`category_service.py` 4 处、`custom_record_aggregator.py` 2 处直接 DELETE，需下沉到 Provider。
4. **废弃表**：`category_map_cache`、`daily_focus`、`weekly_focus` 建议确认是否从 SYNC_TABLES 移除。

### 待写 ADR

1. **`2026-07-22-server-providers-migration.md`** — Provider 迁移决策
2. **`2026-07-22-value-commitment-cascade-refactor.md`** — 级联删除协同设计
3. **`2026-07-22-db-cascade-removal.md`** — 移除 DB CASCADE 决策

### 实施顺序

1. 基类改造：`_generic_delete` 写墓碑 + 实现 `_generic_batch_delete`（前置，必须先完成）
2. P1 JournalProvider 迁移（与 PRD 1 并行，TEXT 主键）
3. P2 CommitmentProvider 迁移（与 PRD 1 并行，TEXT 主键）
4. P3 BeingProvider 迁移（依赖 PRD 1 完成，**AUTOINCREMENT 表，create 必须走 _generic_insert**）
5. P4 ValueProvider 迁移（依赖 P2）
6. W2 审计：repository/providers/ 下 6 张 AUTOINCREMENT 表的 create 通道
7. L1 单表单条删除 13 处改造（与 P1-P4 协同，部分在迁移时处理）
8. L2 批量删除 12 处改造
9. L3 级联删除 4 处表组改造
10. L4 Service/Aggregator 层 6 处直接 DELETE 下沉到 Provider
11. grep 全局验证：无残留的 `DELETE FROM` SYNC_TABLES 原生 SQL
12. P5 StatisticalDataProviders 迁移（单独 PRD）

### 验收标准

#### 基类方法验收

- [ ] `_generic_insert` 对 AUTOINCREMENT 表自动生成 `hash_id`（PRD 1 已实现，验证不回退）
- [ ] `_generic_delete` 对 SYNC_TABLES 在删除前写墓碑
- [ ] `_generic_delete` 对非 SYNC_TABLES 不写墓碑
- [ ] AUTOINCREMENT 表删除时墓碑 `record_id` 为 `hash_id`
- [ ] `_generic_batch_delete` 实现并测试
- [ ] 移除 `habit_chain_nodes` 的 DB CASCADE

#### P1-P4 验收

- [ ] 4 个 Provider 迁移到 `repository/providers/`
- [ ] 所有方法改用 `_generic_*`
- [ ] API 端点行为等价
- [ ] CommitmentProvider 新增 3 个级联方法
- [ ] ValueProvider 级联删除重构

#### 写入通道统一验收（_generic_insert 保障 hash_id）

- [ ] P1-P4 迁移后所有 create 走 `_generic_insert`
- [ ] repository/providers/ 下 6 张 AUTOINCREMENT 表的 Provider create 全部走 `_generic_insert`
- [ ] 无绕过 `_generic_insert` 直接执行 `INSERT INTO` 的写入路径
- [ ] `SyncRepository.upsert_rows_with_lww` 的 hash_id 逻辑正常

#### 删除通道统一验收

- [ ] **31 处不合规删除全部改用 `_generic_delete` / `_generic_batch_delete`**（全局审计覆盖所有 31 张 SYNC_TABLES）
- [ ] L1 单表单条删除 13 处全部改造
- [ ] L2 批量删除 12 处全部改造
- [ ] L3 级联删除 4 处表组全部改造（为每张子表写墓碑）
- [ ] L4 Service/Aggregator 层 6 处直接 DELETE 下沉到 Provider
- [ ] grep 验证：`lifeprism/` 目录下（排除 migrations/、api/、test/、SyncRepository.full_clear）无残留的 `DELETE FROM` SYNC_TABLES 原生 SQL
- [ ] grep 验证：`lifeprism/` 目录下无残留的 `self.db.delete(` 调用 SYNC_TABLES
- [ ] 级联删除为所有 SYNC_TABLES 分别写墓碑
- [ ] 云端 `full_clear` 和迁移脚本 DELETE 不写墓碑

### 已知风险

1. **测试覆盖率为 0%**：5 个 Provider 无任何测试，迁移前必须补基线测试。
2. **异常行为变化**：静默返回 None/False 改为抛 `DataAccessError`，service 层需适配。
3. **`_ON_CONFLICT` 默认值风险**：ValueProvider 必须显式 `_ON_CONFLICT = "abort"`。
4. **级联删除事务原子性**：暂不处理，后续补。
