---
version: 1.0
created_at: 2026-07-24
updated_at: 2026-07-24
last_updated: 初版，基于删除端点墓碑写入端到端测试报告建立预防性规则
abstract: 面向新增 SYNC_TABLES 和修改删除逻辑的开发者与 AI，规定新表接入同步时必须提供走墓碑通道的删除方法，旧表修改删除逻辑时必须验证墓碑写入，防止删除操作绕过墓碑导致云端数据"复活"。
---

# 墓碑同步预防性规则

## 触发条件

遇到以下任一场景时，必须阅读并遵循本文档：

- 创建新的数据库表并计划加入 `SYNC_TABLES`
- 为已有 SYNC_TABLES 新增删除方法（含软删除、级联删除、批量删除）
- 修改已有删除方法的实现（如从 `_generic_delete` 改为原生 SQL）
- 修改 `_generic_delete` / `_generic_batch_delete` 基类行为
- 修改 `SYNC_TABLES` 或 `HASH_ID_PREFIXES` 列表
- 编写 Service/Aggregator 层的级联删除或隐蔽删除逻辑

本文档补充 [`sync-friendly-table-design.md`](./sync-friendly-table-design.md)；后者关注建表规则，本文档关注**删除操作必须写入墓碑**的预防性约束。

## 背景

PRD2（deletion-sync-02-code）要求所有 SYNC_TABLES 的删除必须走 `_generic_delete` / `_generic_batch_delete` 通道以自动写入墓碑。若删除操作绕过墓碑通道，本地删除无法同步到云端，云端数据会"复活"。历史上已发现多起遗漏案例（见 [测试报告](../general/023/2026-07-24-delete-endpoints-tombstone-e2e-test-report.md)）。

## 核心规则

### 规则 1：新同步表必须提供走墓碑通道的删除方法

将新表加入 `SYNC_TABLES` 前，逐项确认：

- [ ] 是否已实现 `delete` 方法并调用 `_generic_delete` 或 `_generic_batch_delete`？
- [ ] 若表使用 AUTOINCREMENT，`hash_id` 是否已注册到 `HASH_ID_PREFIXES`？（删除时墓碑 record_id 使用 hash_id）
- [ ] 若为动态表（`custom_<slug>`），是否通过 `write_tombstone_with_cursor` 显式写墓碑？
- [ ] 是否有端到端测试验证删除后 `deletion_log` 表中存在对应墓碑？

**禁止**：新同步表的删除方法直接执行 `DELETE FROM` 原生 SQL 而不写墓碑。

**例外**：以下场景不写墓碑属于设计意图，但必须在 ADR 或代码注释中明确说明：
- 表本身不同步（不在 SYNC_TABLES 中）
- 墓碑表自身清理（`deletion_log` 的 `cleanup_before`）
- 全量清空场景（`sync_full_clear`）
- 墓碑执行删除（`execute_tombstone_delete`，墓碑已存在）

### 规则 2：旧同步表修改删除逻辑必须验证墓碑写入

修改已有 SYNC_TABLES 的删除方法时：

- [ ] 若实现方式从 `_generic_delete` 改为其他（如原生 SQL），必须保留墓碑写入逻辑
- [ ] 若新增级联删除分支，每个分支的删除都必须走墓碑通道
- [ ] 若新增批量删除方法，必须使用 `_generic_batch_delete` 或显式批量写墓碑
- [ ] 修改后必须运行墓碑测试验证：`python -m pytest test/core/unit/storage/ -v -k tombstone`

### 规则 3：Service/Aggregator 层隐蔽删除必须走墓碑

Service 层和 Aggregator 层的删除逻辑容易遗漏墓碑：

#### 3.1 级联删除

级联删除中**每个被删除的表**都必须走墓碑通道：

```python
# 正确：每个表都走 _generic_delete / _generic_batch_delete
def delete_value_with_cascade(self, value_id):
    self.commitment_provider.delete_by_value_id(value_id)  # 走 _generic_batch_delete
    self.value_provider.delete_value(value_id)             # 走 _generic_delete

# 错误：级联表直接执行 DELETE FROM 不写墓碑
def delete_value_with_cascade(self, value_id):
    self.db.execute("DELETE FROM commitments WHERE value_id = ?", (value_id,))  # 禁止
    self.value_provider.delete_value(value_id)
```

#### 3.2 软删除（逻辑删除）

软删除（`UPDATE ... SET state=0` 或 `UPDATE ... SET status='deleted'`）**不写墓碑**，因为记录仍存在。这是允许的，但需注意：

- 软删除不会同步到云端，云端记录仍为活跃状态
- 若业务要求软删除也同步，必须改为物理删除走墓碑，或设计独立的软删除同步机制
- 必须在代码注释中说明"软删除不写墓碑"的设计意图

#### 3.3 同步触发的删除

同步流程中的删除（如 `_pull_deletion_log`、`sync_push_deletion_log`）使用 `execute_tombstone_delete_with_cursor`，**不写墓碑**（因为墓碑已存在）。这是正确的，但禁止将这些方法用于非同步场景的删除。

### 规则 4：禁止绕过墓碑通道的删除模式

以下删除模式**严格禁止**用于 SYNC_TABLES：

| 禁止模式 | 原因 | 正确做法 |
|---------|------|---------|
| `cursor.execute("DELETE FROM ...")` 原生 SQL | 不写墓碑 | 使用 `_generic_delete` |
| `self.db.delete(table, where)` | 不写墓碑 | 使用 `_generic_delete` |
| `self.db.delete_by_id(table, col, id)` | 不写墓碑 | 使用 `_generic_delete` |
| `UPDATE ... SET state=0` 伪装删除 | 不删除记录，不写墓碑 | 若需同步，改为物理删除 |
| `DROP TABLE` 用于同步表 | DDL 不写墓碑 | 逐行删除走 `_generic_delete` |

**例外**：`DROP TABLE` 用于动态表（`custom_<slug>`）是允许的，因为动态表不在 SYNC_TABLES 中。

### 规则 5：新增删除方法的检查清单

编写新的删除方法时，逐项确认：

- [ ] 目标表是否在 `SYNC_TABLES` 中？若是，必须走墓碑通道
- [ ] 是否调用了 `_generic_delete` / `_generic_batch_delete`？
- [ ] 若为动态表，是否调用了 `write_tombstone_with_cursor`？
- [ ] 若为批量删除，是否为每条记录分别写墓碑？
- [ ] 若为级联删除，每个被删表是否都走墓碑？
- [ ] 墓碑的 `target_table` 是否正确？
- [ ] 墓碑的 `record_id` 是否正确（TEXT 主键=主键值，AUTOINCREMENT=hash_id）？
- [ ] 是否编写了端到端测试验证墓碑写入？

### 规则 6：墓碑测试覆盖要求

墓碑测试分为四个层级，新增删除方法必须补充对应层级的测试：

| 层级 | 测试文件 | 覆盖范围 |
|------|---------|---------|
| L1 | test_l1_remaining_delete_tombstone.py | 单条删除（TEXT 主键 + AUTOINCREMENT） |
| L2 | test_l2_batch_delete_tombstone.py | 批量删除 |
| L3 | test_l3_cascade_delete_tombstone.py | 级联删除 |
| L4 | test_l4_category_service_delete_sink.py | Service 层隐蔽删除 |
| E2E | test_delete_endpoints_tombstone_e2e.py | 所有删除端点综合覆盖 |

测试必须验证：
1. 删除后记录消失
2. `deletion_log` 表中有对应墓碑
3. 墓碑 `target_table`、`record_id`、`source="local"` 正确
4. 不写墓碑的场景（如软删除）验证 `deletion_log` 无墓碑

## 审计参考

完整删除端点审计结果见 [删除端点墓碑写入端到端测试报告](../general/023/2026-07-24-delete-endpoints-tombstone-e2e-test-report.md)。

## 相关文档

- [ADR: deletion-sync-tombstone](../adr/2026-07-22-deletion-sync-tombstone.md)
- [ADR: deletion-log-table](../adr/2026-07-22-deletion-log-table.md)
- [ADR: hash-id-sync-only-identifier](../adr/2026-07-22-hash-id-sync-only-identifier.md)
- [规则: 同步友好建表规则](./sync-friendly-table-design.md)
- [规则: 建表规则](./create-table-rules.md)
- [已知限制: habit-chain-tables-not-synced](../known-limitations/habit-chain-tables-not-synced.md)
