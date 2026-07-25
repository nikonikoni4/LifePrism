---
title: ComputerUsageProvider 补 5 个缺口方法 + Aggregator 委托 + 单元测试
created_at: 2026-07-23
status: ready-for-agent
---

## Parent

`.scratch/deletion-sync-02a-statistical/prd.md`（同步删除 - 阶段 2a：StatisticalDataProviders 迁移 P5）

## What to build

在 `lifeprism/repository/providers/computer_usage_provider.py` 新增 5 个方法，覆盖批量操作、动态 WHERE、聚合查询三类缺口。**同时**在 `lifeprism/repository/aggregators/computer_usage_aggregator.py` 添加 5 个委托方法（与 Provider 方法同名），内部委托给 `self.computer_usage_provider.xxx(...)`。

这是 Slice 04 和 Slice 05 的预重构（prefactoring）——先补齐 Provider + Aggregator 两层能力，再迁移调用方。

**重要**：`lifeprism/repository/__init__.py:44` 中 `computer_usage_repository` 实际是 **Aggregator 单例**（`computer_usage_aggregator`），不是 Provider 单例。调用方（Slice 04/05）通过 `computer_usage_repository.xxx(...)` 调用，因此 Aggregator 必须暴露这 5 个委托方法，否则会 AttributeError。

新增方法签名与语义详见 PRD 的 Implementation Decisions 章节，摘要如下：

### Provider 层（`computer_usage_provider.py`）

1. **`batch_update_computer_usage(record_ids: list[str], data: dict[str, Any]) -> int`**：批量更新记录，动态构建 `SET` 子句 + `IN` 占位符，单次 SQL。不自动更新 `updated_at`（由调用方决定）。

2. **`batch_delete_computer_usage(record_ids: list[str]) -> int`**：批量删除记录，调用基类 `_generic_batch_delete(record_ids)`，内部为每条记录写墓碑到 `deletion_log` + 批量 DELETE 在同一事务。

3. **`update_by_filter(set_fields: dict[str, Any], where_conditions: dict[str, Any]) -> int`**：按条件更新记录（动态 WHERE）。支持操作符后缀（如 `"start_time >="`）。`where_conditions` 的 key 必须在 `_FILTER_FIELDS` 白名单内（校验时先剥除操作符后缀再比对，见下方说明）。`set_fields` 中 None 值表示清除该字段为 NULL。

4. **`get_total_duration(start_utc: str, end_utc: str) -> int`**：返回时间范围内总活跃时长（秒），无数据返回 0。`SELECT SUM(duration) FROM user_app_behavior_log WHERE start_time >= ? AND start_time <= ?`。时区转换由 Service 层完成，Provider 只接收 UTC。

5. **`get_top_groups_by_duration(group_field: str, start_utc: str, end_utc: str, top_n: int) -> list[tuple[str, int]]`**：按指定字段分组聚合 Top N，返回 `[(name, duration), ...]` 按 duration 降序。合并了原 `get_top_applications` 和 `get_top_title`，通过 `group_field` 参数区分。`group_field` 必须在 `_FILTER_FIELDS` 白名单内。

### Aggregator 层（`computer_usage_aggregator.py`）

为上述 5 个方法各添加一个同名的委托方法，内部委托给 `self.computer_usage_provider.xxx(...)`。参照 Aggregator 中现有的 `update_computer_usage` / `delete_computer_usage` 委托模式实现。

### `_FILTER_FIELDS` 白名单说明

**复用** `ComputerUsageProvider` 已有的 `_FILTER_FIELDS` 白名单（位于 `computer_usage_provider.py:33-44`），已包含所有需要的字段：`id`、`start_time`、`end_time`、`duration`、`app`、`title`、`is_multipurpose_app`、`category_id`、`sub_category_id`、`link_to_goal_id`。**无需新增或修改白名单**。

**操作符后缀处理规则**：`update_by_filter` 接收的 `where_conditions` key 可能带操作符后缀（如 `"start_time >="`、`"start_time <="`、`"app"` 无后缀）。校验白名单时应：
1. 检查 key 是否以 ` >=`、` <=`、` >`、` <`、` !=` 结尾
2. 若是，剥除后缀得到字段名（如 `"start_time >="` → `"start_time"`）
3. 将剥除后的字段名与 `_FILTER_FIELDS` 比对
4. 不在白名单内的字段抛出 `ValueError` 或 `DataAccessError`

## Acceptance criteria

### Provider 层

- [ ] `ComputerUsageProvider` 新增 5 个方法
- [ ] `batch_delete_computer_usage` 验证写墓碑到 `deletion_log` 表（N 条记录对应 N 条墓碑）
- [ ] `update_by_filter` 支持 None 值清除字段为 NULL
- [ ] `update_by_filter` 支持带操作符后缀的 key（如 `"start_time >="`）
- [ ] `update_by_filter` 接收带操作符后缀的 key 时正确剥除后缀并校验白名单
- [ ] `update_by_filter` 对不在 `_FILTER_FIELDS` 白名单内的 key 拒绝执行（抛出异常）
- [ ] `get_top_groups_by_duration` 按 app 分组 + 按 title 分组均正确
- [ ] `get_top_groups_by_duration` 结果按 duration 降序 + top_n 限制生效
- [ ] `get_total_duration` 无数据时返回 0

### Aggregator 层

- [ ] `ComputerUsageAggregator` 新增 5 个委托方法（与 Provider 方法同名）
- [ ] 调用方通过 `computer_usage_repository.xxx(...)` 可成功调用 5 个新方法（即 `computer_usage_repository.batch_update_computer_usage(...)` 等均可正常调用）
- [ ] Aggregator 委托方法内部正确转发参数给 `self.computer_usage_provider.xxx(...)`

### 测试与回归

- [ ] 5 个方法均有单元测试（位置：`test/core/unit/storage/test_computer_usage_provider.py`，同时测试 Provider 和 Aggregator 两层）
- [ ] 现有测试全部通过（无回归）

## Blocked by

None - can start immediately（PRD 2 基类改造 `_generic_batch_delete` 已完成）
