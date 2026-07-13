# 时间格式不一致导致 SQL 字符串比对丢失数据

## 元信息

| 问题 | 类型 | 严重程度 |
|------|------|---------|
| `sync_service.py` end_time 格式不一致 | **代码 bug**（已修复） | 🔴 高（07-13 数据被静默排除） |
| `screen_capture_provider.py` ISO→空格转换 | **代码 bug**（未修复） | 🔴 高（截图查询可能丢数据） |
| `category_service.py` strftime 空格格式 | **代码 bug**（未修复） | 🔴 高（行为日志查询可能丢数据） |
| `usage_service.py` / `activity_stats_builder.py` / `report_service.py` normalize | 格式不一致 | 🟡 中（仅用于内存过滤，不受影响） |

- **发现时间**: 2026-07-13
- **修复状态**: `sync_service.py` 已修复，其余待修复

## 问题描述

### 根因：ISO 8601 格式（`T` 分隔符）与空格格式的字符串比对陷阱

数据库存储的时间统一为 UTC ISO 8601 格式（`YYYY-MM-DDTHH:MM:SS.ffffff+00:00`）。SQLite 进行字符串比对时，`T` 的 ASCII 码（84）**大于**空格的 ASCII 码（32），导致：

```
'2026-07-13T08:18:40+00:00' > '2026-07-13 08:19:32+00:00'
         ^                                  ^
       T (84)                            空格 (32)
```

当 WHERE 条件为 `start_time <= '2026-07-13 ...'`（空格格式）时，所有带 `T` 的记录都被排除。

### 实例 1：`sync_service.py` `screen_behavior_anlysis`（已修复 ✅）

**文件**: [sync_service.py](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/server/services/sync_service.py#L35-L36)（修复前）

原代码将 `T` 替换为空格后，仅对 `start_time` 重新 `.isoformat()`，`end_time` 保持空格格式进入 SQL：

```python
# ❌ 修复前
start_time = start_time.replace("T", " ")   # → "2026-07-10 08:19:32+00:00"
end_time = end_time.replace("T", " ")        # → "2026-07-13 08:19:32+00:00"
start_time = max(...).isoformat()            # → "2026-07-10T08:19:32+00:00" (覆盖)
# end_time 未被覆盖 → 空格格式进入 SQL
```

**后果**：`WHERE start_time <= '2026-07-13 08:19:32...'` → 07-13 全部 167 条记录被排除。

**修复**：用 `_to_utc_iso()` 统一归一化两个时间，复用 `local_to_utc_iso()`。

### 实例 2：`screen_capture_provider.py` `query_screenshots`（⚠️ 未修复）

**文件**: [screen_capture_provider.py](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/repository/providers/screen_capture_provider.py#L230-L231)

```python
# ❌ 将 ISO 转为空格后再传入 QueryOptions
start_time_db = start_time.replace("T", " ") if "T" in start_time else start_time
end_time_db = end_time.replace("T", " ") if "T" in end_time else end_time

options = QueryOptions(
    time_range=(start_time_db, end_time_db),  # → WHERE captured_at >= ? AND captured_at <= ?
)
```

`screen_captures.captured_at` 存储的是 ISO 格式（`2026-07-13T00:30:12+00:00`），查询参数却是空格格式。

**已验证**：同一 chunk 范围内，ISO 格式查出 3 条，空格格式查出 0 条。

**后果**：即使 `sync_service.py` 修复后能正确识别 07-13 的高密度段，`query_screenshots` 仍可能查不到截图。

**修复建议**：直接传 ISO 格式，不转换。

### 实例 3：`category_service.py` `get_category_stats`（⚠️ 未修复）

**文件**: [category_service.py](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/server/services/category_service.py#L192-L193)

```python
# ❌ 用 strftime 产生空格格式，传入 load_user_app_behavior_log 直接绑参 SQL
start_time_str = start_time.strftime("%Y-%m-%d %H:%M:%S")
end_time_str = end_time.strftime("%Y-%m-%d %H:%M:%S")

behavior_df = self.server_lw_data_provider.load_user_app_behavior_log(
    start_time=start_time_str, end_time=end_time_str
)
```

`load_user_app_behavior_log` 直接将参数绑入 SQL：`WHERE start_time >= ? AND end_time <= ?`（[lw_base_data_provider.py#L765-L771](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/repository/base_providers/lw_base_data_provider.py#L765-L771)）

**后果**：同模式，可能丢失数据。

**修复建议**：用 `.isoformat()` 替代 `.strftime()`。

### 实例 4-6：`_normalize_timestamp` / `_normalize_created_at`（🟡 中风险）

**文件**:
- [usage_service.py#L47](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/server/services/usage_service.py#L47)
- [activity_stats_builder.py#L45](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/server/services/activity_stats_builder.py#L45)
- [report_service.py#L74](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/server/services/report_service.py#L74)

这些函数在内存中对**已加载的**数据进行 `replace("T", " ", 1)` 归一化，用于字符串比对。因为输入和比对目标都经过同样的归一化处理，目前功能正确。但格式不一致违反 [time-handling-rules.md](file:///d:/desktop/软件开发/LifeWatch-AI/docs/coding-rules/time-handling-rules.md) Rule 3.2。

## 影响

1. **数据丢失**（实例 1-3）：SQL 字符串比对排除理应命中的记录，导致截图分析、分类统计等功能静默返回空结果
2. **隐蔽性**：不报错、不抛异常，仅在"结果为空"时才能察觉
3. **蔓延性**：任何将 ISO 格式转为空格后再用于 DB 查询的代码路径都可能受影响

## 为什么容易出错

数据库层面 SQLite 不区分时间类型，时间字段存为 TEXT，字符串比对依赖词法序（lexicographic order）。ISO 8601 格式（`T` 分隔）恰好满足词法序 = 时间序，但空格格式破坏了这一性质：

```
正确（ISO）:    2026-07-13T00:30:00 < 2026-07-13T01:00:00  ✅
破坏（空格）:   2026-07-13 00:30:00 <  2026-07-13T01:00:00  ❌（空格 < T，但实际时间相反）
```

## 修复计划

| 实例 | 文件 | 状态 | 建议修复 |
|------|------|------|---------|
| 1 | `sync_service.py` | ✅ 已修复 | 已完成 |
| 2 | `screen_capture_provider.py:230-231` | ❌ 待修复 | 删除 `replace("T", " ")`，直接传 ISO |
| 3 | `category_service.py:192-193` | ❌ 待修复 | `strftime` → `.isoformat()` |
| 4-6 | `usage_service.py` / `activity_stats_builder.py` / `report_service.py` | 🟡 可选 | 用 `parse_iso_to_aware` 代替字符串归一化 |

## 预防措施

已更新 [lifeprism/CLAUDE.md](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/CLAUDE.md) 新增时间处理规则，要求涉及时间处理时必须：

1. 阅读 `docs/coding-rules/time-handling-rules.md`
2. 查阅 `lifeprism/utils/time_utils.py`，优先复用已有函数，禁止手写时区转换逻辑

## 相关文档

- 时间处理规则：`docs/coding-rules/time-handling-rules.md`
- 时间工具函数：`lifeprism/utils/time_utils.py`
- 后端规则（时间处理节）：`lifeprism/CLAUDE.md#时间处理`
- 本次修复的 bug 记录：`docs/history-bugs/2026-07-13-timeline-custom-block-date-query-datetime-field.md`
