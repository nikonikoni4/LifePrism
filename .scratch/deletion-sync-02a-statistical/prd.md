---
title: 同步删除 - 阶段 2a：StatisticalDataProviders 迁移（P5 详细实现）
created_at: 2026-07-22
updated_at: 2026-07-22
status: ready-for-agent
type: refactor
---

# 同步删除 - 阶段 2a：StatisticalDataProviders 迁移（P5 详细实现）

## 总任务说明

本 PRD 是"数据库删除同步"任务链**第 2 步的子 PRD（P5）**，是 [deletion-sync-02-code](../deletion-sync-02-code/prd.md) 的详细实现版本。

```
[PRD 1] Schema 变更（已完成）
    │   6 张 AUTOINCREMENT 表加 hash_id 字段
    │   新增 deletion_log 墓碑表
    ▼
[PRD 2] 代码适配（进行中）
    │   P1 JournalProvider（独立）
    │   P2 CommitmentProvider（独立）
    │   P3 BeingProvider（依赖 PRD 1）
    │   P4 ValueProvider（依赖 P2）
    │   P5 StatisticalDataProviders ← 本 PRD
    ▼
[PRD 3] 墓碑同步流程
```

**本 PRD 的边界**：将 `server/providers/statistical_data_providers.py` 中 10 个业务使用方法迁移到 `ComputerUsageProvider` / `ComputerUsageAggregator` / Service 层，删除 11 个死代码方法，删除原文件。迁移后的删除通道走 `_generic_delete` / `_generic_batch_delete`（含写墓碑），但墓碑的同步传播流程属于 PRD 3。

## Problem Statement

`lifeprism/server/providers/statistical_data_providers.py` 是 repo 模块迁移时遗漏的技术债，存在三个问题：

1. **52% 死代码**：21 个方法中 11 个无任何调用方（4 个 tokens_usage_log、4 个 category_map_cache、3 个杂项），占据代码篇幅但无实际价值。

2. **业务逻辑错放在 Provider**：10 个业务使用方法中，时区转换、goal_id 三态语义、is_multipurpose_app 判断、百分比计算等业务逻辑被硬编码在 Provider 层，违反了"Provider 只负责数据访问，业务逻辑上移到 Service"的分层原则。

3. **删除通道不一致**：`delete_event` / `batch_delete_events` 使用原生 SQL DELETE，不走 `_generic_delete` / `_generic_batch_delete`，删除时不会写墓碑到 `deletion_log`，导致删除同步失败。

## Solution

### 三部分工作

1. **删死代码**：删除 11 个无调用方的方法（可独立先行）。
2. **补 Provider 缺口**：在 `ComputerUsageProvider` 新增 5 个方法，覆盖批量操作、动态 WHERE、聚合查询三类缺口。
3. **迁移调用方 + 业务逻辑上移**：将 2 个 Service 文件的 11 处调用迁移到新方法，同时将 5 类业务逻辑上移到 Service 层。

### 方法迁移分类

| 类别 | 方法数 | 处理方式 |
|------|--------|---------|
| 可完全替代（已存在方法） | 4 | 调用方直接改用 `ComputerUsageAggregator` / `ComputerUsageProvider` 现有方法 |
| 需新增 Provider 方法 | 5（对应原 6 个方法） | 在 `ComputerUsageProvider` 新增 5 个方法 |
| 死代码 | 11 | 直接删除 |
| 业务逻辑上移 | 5 类 | 从 Provider 上移到 Service 层 |

## User Stories

### 阶段 1：删除死代码

1. 作为系统维护者，删除 `get_range_active_time`（无调用方）。
2. 作为系统维护者，删除 `get_category_stats`（已被 `CategoryService.get_category_stats` 替代）。
3. 作为系统维护者，删除 `get_app_usage_summary`（无调用方）。
4. 作为系统维护者，删除 4 个 tokens_usage_log 方法（`get_tokens_usage`、`get_all_tokens_usage`、`get_tokens_usage_by_mode`、`get_all_tokens_usage_by_mode`，全部无调用方）。
5. 作为系统维护者，删除 4 个 category_map_cache 方法（`update_category_map_cache_by_id`、`batch_update_category_map_cache_by_ids`、`delete_category_map_cache_by_id`、`batch_delete_category_map_cache_by_ids`，全部已被 `map_cache_repository` 替代）。
6. 作为系统维护者，删除 `__main__` 测试块（调用了不存在的方法 `get_timeline_events_by_date`）。

### 阶段 2：补 Provider 缺口方法

7. 作为系统开发者，在 `ComputerUsageProvider` 新增 `batch_update_computer_usage(record_ids: list[str], data: dict[str, Any]) -> int`，批量更新记录。
8. 作为系统开发者，在 `ComputerUsageProvider` 新增 `batch_delete_computer_usage(record_ids: list[str]) -> int`，走 `_generic_batch_delete` 写墓碑。
9. 作为系统开发者，在 `ComputerUsageProvider` 新增 `update_by_filter(set_fields: dict, where_conditions: dict) -> int`，支持动态 WHERE 更新。
10. 作为系统开发者，在 `ComputerUsageProvider` 新增 `get_total_duration(start_utc: str, end_utc: str) -> int`，返回时间范围内总活跃时长（秒）。
11. 作为系统开发者，在 `ComputerUsageProvider` 新增 `get_top_groups_by_duration(group_field: str, start_utc: str, end_utc: str, top_n: int) -> list[tuple[str, int]]`，按指定字段分组聚合 Top N。

### 阶段 3：迁移调用方（4 个可完全替代方法）

12. 作为系统开发者，`activity_service.get_activity_log_detail` 改用 `ComputerUsageAggregator.get_computer_usage_by_id_with_names(log_id)`。
13. 作为系统开发者，`activity_service.update_log_category` 改用 `ComputerUsageProvider.update_computer_usage(record_id, {"category_id":..., "sub_category_id":...})`。
14. 作为系统开发者，`activity_service.delete_log` 改用 `ComputerUsageProvider.delete_computer_usage(record_id)`（走 `_generic_delete` 写墓碑）。
15. 作为系统开发者，`activity_stats_builder.build_activity_summary` 改用 `load_user_app_behavior_log` 取 DataFrame + Service 层 Python 聚合（复用已有的 `_add_local_date_column` + `groupby`）。

### 阶段 3：迁移调用方（5 个需新增方法）

16. 作为系统开发者，`activity_service.batch_update_log_category` 改用 `ComputerUsageProvider.batch_update_computer_usage(record_ids, data)`。
17. 作为系统开发者，`activity_service.batch_delete_logs` 改用 `ComputerUsageProvider.batch_delete_computer_usage(record_ids)`（走 `_generic_batch_delete` 写墓碑）。
18. 作为系统开发者，`activity_service.update_logs_by_app_title` 改用 `ComputerUsageProvider.update_by_filter(set_fields, where_conditions)`，goal_id 三态语义 + is_multipurpose_app 判断上移到 Service 层。
19. 作为系统开发者，`activity_stats_builder.get_top_app` 改用 `ComputerUsageProvider.get_top_groups_by_duration("app", start_utc, end_utc, top_n)`，时区转换 + 字段名映射上移到 Service 层。
20. 作为系统开发者，`activity_stats_builder.get_top_title` 改用 `ComputerUsageProvider.get_top_groups_by_duration("title", start_utc, end_utc, top_n)`，时区转换 + 字段名映射上移到 Service 层。
21. 作为系统开发者，`activity_stats_builder` 中 `get_top_app` / `get_top_title` 调用的 `get_active_time`（用于百分比计算）改用 `ComputerUsageProvider.get_total_duration(start_utc, end_utc)`，时区转换上移到 Service 层。

### 阶段 4：清理

22. 作为系统维护者，删除 `statistical_data_providers.py` 文件。
23. 作为系统维护者，清理 `lifeprism/server/providers/__init__.py` 中 `server_lw_data_provider` 的导入和导出。
24. 作为系统维护者，清理 `activity_service.py` 和 `activity_stats_builder.py` 中 `server_lw_data_provider` 的导入。

## Implementation Decisions

### 5 个新增方法的签名与语义

#### 1. `batch_update_computer_usage`

```python
def batch_update_computer_usage(self, record_ids: list[str], data: dict[str, Any]) -> int:
    """
    批量更新记录

    Args:
        record_ids: 记录 ID 列表
        data: 要更新的字段（如 {"category_id":..., "sub_category_id":...}）

    Returns:
        int: 受影响行数
    """
```

实现：动态构建 `SET` 子句 + `IN` 占位符，单次 SQL。不自动更新 `updated_at`（由调用方决定是否传入）。

#### 2. `batch_delete_computer_usage`

```python
def batch_delete_computer_usage(self, record_ids: list[str]) -> int:
    """
    批量删除记录（走 _generic_batch_delete 写墓碑）

    Args:
        record_ids: 记录 ID 列表

    Returns:
        int: 删除行数
    """
```

实现：调用基类 `_generic_batch_delete(record_ids)`，内部为每条记录写墓碑 + 批量 DELETE 在同一事务。

#### 3. `update_by_filter`

```python
def update_by_filter(self, set_fields: dict[str, Any], where_conditions: dict[str, Any]) -> int:
    """
    按条件更新记录（动态 WHERE）

    Args:
        set_fields: 要更新的字段（None 值表示清除该字段为 NULL）
        where_conditions: WHERE 条件（如 {"app":..., "title":..., "start_time >=":..., "start_time <=":...}）

    Returns:
        int: 受影响行数
    """
```

实现：动态构建 `SET` + `WHERE` 子句。支持操作符后缀（如 `"start_time >="`）。**注意**：调用方需确保 `where_conditions` 的 key 在 `_FILTER_FIELDS` 白名单内。

#### 4. `get_total_duration`

```python
def get_total_duration(self, start_utc: str, end_utc: str) -> int:
    """
    获取时间范围内总活跃时长

    Args:
        start_utc: 开始时间（UTC ISO 8601）
        end_utc: 结束时间（UTC ISO 8601）

    Returns:
        int: 总时长（秒），无数据返回 0
    """
```

实现：`SELECT SUM(duration) FROM user_app_behavior_log WHERE start_time >= ? AND start_time <= ?`。**时区转换由 Service 层完成**，Provider 只接收 UTC。

#### 5. `get_top_groups_by_duration`

```python
def get_top_groups_by_duration(
    self, group_field: str, start_utc: str, end_utc: str, top_n: int
) -> list[tuple[str, int]]:
    """
    按指定字段分组聚合 Top N

    Args:
        group_field: 分组字段（如 "app" 或 "title"）
        start_utc: 开始时间（UTC ISO 8601）
        end_utc: 结束时间（UTC ISO 8601）
        top_n: 返回前 N 条

    Returns:
        list[tuple[str, int]]: [(name, duration), ...]，按 duration 降序
    """
```

实现：`SELECT {group_field}, CAST(SUM(duration) AS INTEGER) FROM ... WHERE ... GROUP BY {group_field} ORDER BY ... DESC LIMIT ?`。**合并了原 `get_top_applications` 和 `get_top_title`**，通过 `group_field` 参数区分。`group_field` 必须在 `_FILTER_FIELDS` 白名单内。

### 业务逻辑上移清单（含精确落地位置）

每个业务逻辑必须明确写到具体的文件和函数，不能笼统说"上移到 Service 层"。

#### 上移点 1：时区转换（`current_date` setter → `build_utc_time_range`）

| 原方法 | 原位置 | 落地文件 | 落地函数 | 当前代码 | 迁移后代码 |
|--------|--------|---------|---------|---------|----------|
| `get_active_time` 被调用 | `activity_stats_builder.get_top_title` (line 308) | `activity_stats_builder.py` | `get_top_title(date, top_n)` (line 295-322) | `server_lw_data_provider.get_active_time(date)` | `start_utc, end_utc = build_utc_time_range(date)` → `computer_usage_repository.get_total_duration(start_utc, end_utc)` |
| `get_active_time` 被调用 | `activity_stats_builder.get_top_app` (line 338) | `activity_stats_builder.py` | `get_top_app(date, top_n)` (line 325-350) | `server_lw_data_provider.get_active_time(date)` | 同上 |
| `get_top_applications` / `get_top_title` 被调用 | `activity_stats_builder.get_top_app` / `get_top_title` | `activity_stats_builder.py` | 同上两个函数 | `server_lw_data_provider.get_top_applications(date, top_n)` | `start_utc, end_utc = build_utc_time_range(date)` → `computer_usage_repository.get_top_groups_by_duration("app", start_utc, end_utc, top_n)` |

**说明**：`build_utc_time_range` 已在 `activity_stats_builder.py:204` 的 `build_time_overview` 中使用过，导入已存在，直接复用。

#### 上移点 2：goal_id 三态语义（None=不修改 / ""=清除 / "goal-xxx"=设置）

| 原方法 | 原位置 | 落地文件 | 落地函数 | 迁移后代码 |
|--------|--------|---------|---------|----------|
| `update_logs_by_app_title` 内部 (line 451-455) | `statistical_data_providers.py:451-455` | `activity_service.py` | `update_logs_by_app_title(...)` (line 203-242) | 见下方代码示例 |

**迁移后 `activity_service.update_logs_by_app_title` 实现**：

```python
def update_logs_by_app_title(
    app: str,
    title: str | None,
    is_multipurpose_app: bool,
    category_id: str,
    sub_category_id: str | None = None,
    goal_id: str | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
) -> int:
    # 1. 构建 set_fields（goal_id 三态语义在 Service 层处理）
    set_fields = {
        "category_id": category_id,
        "sub_category_id": sub_category_id,
    }
    if goal_id is not None:
        # None=不修改（不加入 set_fields），""=清除（设为 None），"goal-xxx"=设置
        set_fields["link_to_goal_id"] = goal_id if goal_id else None

    # 2. 构建 where_conditions（is_multipurpose_app 判断在 Service 层处理）
    where_conditions = {"app": app}
    if is_multipurpose_app:
        if title is None:
            raise ValueError("多用途应用必须提供 title 参数")
        where_conditions["title"] = title

    # 时间范围（已是 UTC ISO 格式，直接传入）
    if start_time:
        where_conditions["start_time >="] = start_time
    if end_time:
        where_conditions["start_time <="] = end_time

    # 3. 调用 Provider 的通用 update_by_filter
    return computer_usage_repository.update_by_filter(
        set_fields=set_fields,
        where_conditions=where_conditions,
    )
```

#### 上移点 3：is_multipurpose_app 判断

与上移点 2 同一个函数，见上方代码示例的步骤 2。原位置：`statistical_data_providers.py:461-466`，落地到 `activity_service.update_logs_by_app_title`。

#### 上移点 4：百分比计算（`* 100 / 86400`）

| 原方法 | 原位置 | 落地文件 | 落地函数 | 迁移后代码 |
|--------|--------|---------|---------|----------|
| `get_daily_active_time` (line 263) | `statistical_data_providers.py:263` | `activity_stats_builder.py` | `build_activity_summary(date, ...)` (line 120-185) | 见下方代码示例 |

**迁移后 `build_activity_summary` 的步骤 3-4 改造**：

```python
def build_activity_summary(date, history_number, future_number, category_id, sub_category_id):
    # ... 步骤 1-2 不变（计算日期范围）...

    # 3. 查询原始数据（替代原 get_daily_active_time）
    start_utc, _ = build_utc_time_range(start_date)
    _, end_utc = build_utc_time_range(end_date)
    df = computer_usage_repository.load_user_app_behavior_log(
        start_time=start_utc, end_time=end_utc
    )

    # 4. Python 层按本地日期分组 + 计算百分比（业务逻辑上移）
    daily_activities = []
    if df is not None and not df.empty:
        # 复用已有的 _add_local_date_column（activity_stats_builder.py:75-98）
        df = _add_local_date_column(df, "start_time")
        # 按分类筛选（如果有）
        if category_id:
            df = df[df["category_id"] == category_id]
        if sub_category_id:
            df = df[df["sub_category_id"] == sub_category_id]
        # 按本地日期分组求和
        daily_durations = df.groupby("local_date")["duration"].sum().to_dict()
    else:
        daily_durations = {}

    # 5. 构建完整日期数组（缺失日期补 0）+ 百分比计算
    for date_str in date_range:
        total_duration = daily_durations.get(date_str, 0)
        percentage = int(total_duration * 100 / 86400) if total_duration > 0 else 0
        duration = int(percentage * 86400 / 100)
        daily_activities.append(DailyActivitiesData(...))

    return ActivitySummaryData(daily_activities=daily_activities)
```

**关键**：`_add_local_date_column` 已在 `activity_stats_builder.py:75-98` 实现，直接复用。原 `get_daily_active_time` 中的 `utc_to_local_display` 逻辑被 `_add_local_date_column` 的 pandas 向量化实现替代，语义等价。

#### 上移点 5：字段名映射（row → TopAppData/TopTitleData）

| 原方法 | 原位置 | 落地文件 | 落地函数 | 迁移后代码 |
|--------|--------|---------|---------|----------|
| `get_top_applications` 返回 `[{"name":..., "duration":...}]` | `statistical_data_providers.py:68` | `activity_stats_builder.py` | `get_top_app(date, top_n)` (line 325-350) | 见下方代码示例 |
| `get_top_title` 返回 `[{"name":..., "duration":...}]` | `statistical_data_providers.py:96` | `activity_stats_builder.py` | `get_top_title(date, top_n)` (line 295-322) | 同构 |

**迁移后 `get_top_app` 实现**：

```python
def get_top_app(date: str, top_n: int) -> list[TopAppData]:
    # 时区转换上移到 Service 层
    start_utc, end_utc = build_utc_time_range(date)
    # Provider 返回 list[tuple[str, int]]，字段映射在 Service 层
    raw_list = computer_usage_repository.get_top_groups_by_duration(
        "app", start_utc, end_utc, top_n
    )
    total_duration = computer_usage_repository.get_total_duration(start_utc, end_utc)

    result = []
    for name, duration in raw_list:  # tuple 解包，替代原 dict 访问
        result.append(
            TopAppData(
                name=name,
                duration=int(duration),
                percentage=int(duration / total_duration * 100) if total_duration > 0 else 0,
            )
        )
    return result
```

**`get_top_title` 结构完全相同**，只是 `group_field` 传 `"title"` 而非 `"app"`，返回类型是 `TopTitleData`。

### 上移点汇总（一张表看清所有落地位置）

| # | 业务逻辑 | 原文件 | 原函数 | 落地文件 | 落地函数 | 复用的已有能力 |
|---|---------|--------|--------|---------|---------|--------------|
| 1 | 时区转换 | `statistical_data_providers.py` | `get_active_time` / `get_top_*` | `activity_stats_builder.py` | `get_top_app` / `get_top_title` | `build_utc_time_range`（已导入） |
| 2 | goal_id 三态 | `statistical_data_providers.py:451-455` | `update_logs_by_app_title` | `activity_service.py` | `update_logs_by_app_title` (line 203) | 无（纯 Python 逻辑） |
| 3 | is_multipurpose_app | `statistical_data_providers.py:461-466` | `update_logs_by_app_title` | `activity_service.py` | `update_logs_by_app_title` (line 203) | 无（纯 Python 逻辑） |
| 4 | 百分比计算 | `statistical_data_providers.py:263` | `get_daily_active_time` | `activity_stats_builder.py` | `build_activity_summary` (line 120) | `_add_local_date_column` (line 75) + `load_user_app_behavior_log` |
| 5 | 字段名映射 | `statistical_data_providers.py:68,96` | `get_top_applications` / `get_top_title` | `activity_stats_builder.py` | `get_top_app` / `get_top_title` | 无（tuple 解包替代 dict） |

### `get_daily_active_time` 迁移路径（无需新增 Provider 方法）

原方法流程：
1. `build_utc_time_range(start_date, end_date)` → UTC 时间范围
2. SQL 查询 `start_time, duration` 原始数据
3. Python 层 `utc_to_local_display(start_time_iso)[:10]` 按本地日期分组
4. 计算百分比 `int(total_duration * 100 / 86400)`

迁移后流程（Service 层 `activity_stats_builder.build_activity_summary`）：
1. `build_utc_time_range(start_date, end_date)` → UTC 时间范围（**已有**）
2. `computer_usage_repository.load_user_app_behavior_log(start_time, end_time)` → DataFrame（**已有**）
3. `_add_local_date_column(df, "start_time")` → 添加 `local_date` 列（**已有**，`activity_stats_builder.py:75-98`）
4. `df.groupby("local_date")["duration"].sum()` → 按本地日期分组（Service 层新增）
5. `int(total_duration * 100 / 86400)` → 计算百分比（Service 层新增）

**关键**：`_add_local_date_column` 和 `_utc_timestamp_to_local_date` 已在 `activity_stats_builder.py` 中实现，迁移时直接复用。

### `update_event_category` 的 `updated_at` 行为变化

原方法用原生 SQL `UPDATE ... SET category_id=?, sub_category_id=? WHERE id=?`，不更新 `updated_at`。迁移到 `update_computer_usage` 后，基类 `self.db.update` 会自动更新 `updated_at`（因 `user_app_behavior_log` 在 `TABLE_CONFIGS` 中配置了 `update_at: true`）。

**这是 bug 修复**：修改分类应触发云端 LWW 同步，原方法不更新 `updated_at` 会导致云端同步漏掉这次修改。迁移后行为正确。

## Testing Decisions

### 测试接缝

#### S1：5 个新增 Provider 方法

**位置**：`test/core/unit/storage/test_computer_usage_provider.py`（新增或扩展）

**测试内容**：
- `batch_update_computer_usage`：批量更新 + 返回受影响行数
- `batch_delete_computer_usage`：批量删除 + 写墓碑（验证 `deletion_log` 表有 N 条记录）
- `update_by_filter`：动态 WHERE + 操作符后缀 + set_fields 含 None（清除为 NULL）
- `get_total_duration`：时间范围查询 + 无数据返回 0
- `get_top_groups_by_duration`：按 app 分组 + 按 title 分组 + top_n 限制 + 降序

#### S2：Service 层业务逻辑上移

**位置**：`test/core/unit/services/test_activity_service.py`、`test/core/unit/services/test_activity_stats_builder.py`（新增或扩展）

**测试内容**：
- `update_logs_by_app_title` 的 goal_id 三态（None=不修改 / ""=清除 / "goal-xxx"=设置）
- `update_logs_by_app_title` 的 is_multipurpose_app（True=加 title 条件 / False=不加）
- `get_daily_active_time` 迁移后的时区分组正确性（UTC 20:00 的活动应归属本地次日）
- `get_top_app` / `get_top_title` 的百分比计算

#### S3：端到端行为等价

**位置**：`test/core/integration/test_activity_api.py`（新增或扩展）

**测试内容**：
- `/activity/logs/{id}` 返回字段一致（含 `category_name` / `sub_category_name`）
- `/activity/logs` 批量删除后记录消失 + `deletion_log` 有墓碑
- `/activity/stats` 返回数据结构一致

### 测试策略

- **优先补基线测试**：迁移前先对原 `statistical_data_providers.py` 的 10 个方法补基线测试，记录当前行为，作为迁移后行为等价性的对比基准。
- **跨时区测试用例**：`get_daily_active_time` 必须包含 UTC 20:00（本地次日 04:00）的用例，验证时区分组正确。

## Out of Scope

1. **基类 11 个遗留方法**：`load_categories`、`load_sub_categories`、`load_category_map_cache_V2` 等基类方法属于另一个故事，本 PRD 不覆盖。
2. **墓碑同步流程**：sync_once 集成墓碑 Pull/Push/清理，属于 PRD 3。
3. **DeletionLogProvider**：墓碑表 Provider 的 CRUD，属于 PRD 3。
4. `_generic_batch_delete` 基类方法实现：属于 PRD 2 的基类改造，本 PRD 仅调用。

## Further Notes

### 10 个业务方法迁移路径汇总

| # | 原方法 | 调用方 | 迁移路径 | 业务逻辑上移 |
|---|--------|--------|---------|-------------|
| 1 | `get_activity_log_by_id` | `activity_service:161` | `ComputerUsageAggregator.get_computer_usage_by_id_with_names` | 无 |
| 2 | `update_event_category` | `activity_service:182` | `ComputerUsageProvider.update_computer_usage` | 无（updated_at 自动更新是 bug 修复） |
| 3 | `delete_event` | `activity_service:194` | `ComputerUsageProvider.delete_computer_usage` | 无 |
| 4 | `get_daily_active_time` | `activity_stats_builder:155` | `load_user_app_behavior_log` + Service 层聚合 | 时区转换 + 百分比计算 |
| 5 | `batch_update_event_category` | `activity_service:187` | `batch_update_computer_usage`（新增） | 无 |
| 6 | `batch_delete_events` | `activity_service:200` | `batch_delete_computer_usage`（新增） | 无 |
| 7 | `update_logs_by_app_title` | `activity_service:233` | `update_by_filter`（新增） | goal_id 三态 + is_multipurpose_app |
| 8 | `get_active_time` | `activity_stats_builder:310,340` | `get_total_duration`（新增） | 时区转换 |
| 9 | `get_top_applications` | `activity_stats_builder:339` | `get_top_groups_by_duration("app", ...)`（新增） | 时区转换 + 字段映射 |
| 10 | `get_top_title` | `activity_stats_builder:309` | `get_top_groups_by_duration("title", ...)`（新增） | 时区转换 + 字段映射 |

### 11 个死代码方法

| # | 方法名 | 死代码原因 |
|---|--------|-----------|
| 1 | `get_range_active_time` | 无调用方 |
| 2 | `get_category_stats` | 已被 `CategoryService.get_category_stats` 替代 |
| 3 | `get_app_usage_summary` | 无调用方 |
| 4 | `get_tokens_usage` | 无调用方 |
| 5 | `get_all_tokens_usage` | 无调用方 |
| 6 | `get_tokens_usage_by_mode` | 仅被 `get_all_tokens_usage_by_mode` 内部调用（也是死代码） |
| 7 | `get_all_tokens_usage_by_mode` | 无调用方 |
| 8 | `update_category_map_cache_by_id` | 已被 `map_cache_repository` 替代 |
| 9 | `batch_update_category_map_cache_by_ids` | 已被 `map_cache_repository` 替代 |
| 10 | `delete_category_map_cache_by_id` | 已被 `map_cache_repository` 替代 |
| 11 | `batch_delete_category_map_cache_by_ids` | 已被 `map_cache_repository` 替代 |

### 依赖关系

```
P5 迁移
  ├─ 依赖 PRD 1: hash_id + tombstone 表
  │   ├─ batch_delete_computer_usage 需写墓碑（record_id 用 hash_id）
  │   └─ delete_computer_usage 需写墓碑（record_id 用 hash_id）
  │
  ├─ 依赖 PRD 2 基类改造: _generic_batch_delete
  │   └─ batch_delete_computer_usage 基于此实现
  │
  ├─ 依赖 P1-P4 完成（按主计划顺序）
  │
  └─ 独立可执行: 阶段 1（删除 11 个死代码）
      └─ 不影响任何调用方，可单独提交
```

### 实施顺序

1. **阶段 1**：删除 11 个死代码方法（独立可执行，无依赖）
2. **阶段 2**：在 `ComputerUsageProvider` 补 5 个缺口方法 + 单元测试
3. **阶段 3**：迁移 4 个可完全替代方法的调用方 + 业务逻辑上移
4. **阶段 3**：迁移 5 个需新增方法的调用方 + 业务逻辑上移
5. **阶段 4**：删除 `statistical_data_providers.py` + 清理导入

### 验收标准

#### 阶段 1 验收

- [ ] 11 个死代码方法已删除
- [ ] `__main__` 测试块已删除
- [ ] 无调用方报错（grep 验证无残留引用）

#### 阶段 2 验收

- [ ] `ComputerUsageProvider` 新增 5 个方法
- [ ] 5 个方法均有单元测试
- [ ] `batch_delete_computer_usage` 验证写墓碑到 `deletion_log`

#### 阶段 3 验收

- [ ] `activity_service.py` 6 处调用全部迁移
- [ ] `activity_stats_builder.py` 5 处调用全部迁移
- [ ] `get_daily_active_time` 迁移后时区分组正确（跨时区测试通过）
- [ ] `update_logs_by_app_title` 的 goal_id 三态语义保留（测试通过）
- [ ] API 端点行为等价

#### 阶段 4 验收

- [ ] `statistical_data_providers.py` 文件已删除
- [ ] `server/providers/__init__.py` 中 `server_lw_data_provider` 已移除
- [ ] grep 全仓无 `server_lw_data_provider` 残留引用

### 已知风险

1. **`get_daily_active_time` 时区分组逻辑丢失**：迁移时必须保留 Python 层 `utc_to_local_display` 分组，禁止改用 SQL `DATE(start_time)` 分组。缓解：复用 `activity_stats_builder._add_local_date_column` 已有能力 + 跨时区单元测试。
2. **`update_logs_by_app_title` 的 goal_id 三态语义丢失**：迁移时 Service 层必须正确处理 None/""/"goal-xxx" 三种值。缓解：单元测试覆盖三种情况。
3. **`update_event_category` 的 `updated_at` 变化触发 LWW 同步**：原方法不更新 `updated_at`，迁移后会更新。这是 bug 修复，但需验证云端同步行为正常。
4. **基类 11 个方法未处理**：`category_service.py` / `data_processing_service.py` 中对 `server_lw_data_provider` 的基类方法调用（`load_categories` 等）仍需处理，属于另一个故事。
