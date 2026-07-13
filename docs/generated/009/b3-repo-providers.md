# B3: Repository Providers 审查报告

## 审查概要
- 审查文件数: 12
- 审查标准: time-handling-rules.md Section 2, 3.1-3.5
- 变更规模: 大多为机械替换（<35行/文件），集中在时间生成与序列化

---

## 1. 规则遵守程度

### 1.1 goal_providers.py -- ✅ 通过

| 检查项 | 结果 | 位置/说明 |
|--------|------|-----------|
| `datetime.now()` 无时区 | ✅ 已清理 | L495: `datetime.now(timezone.utc)` |
| `strftime()` 残留 | ✅ 已清理 | L820-870: 6处 `strftime("%Y-%m-%d")` → `.date().isoformat()`（日期字段，正确） |
| `.isoformat()` 序列化 | ✅ 正确 | L495: `datetime.now(timezone.utc).isoformat()` |
| `datetime('now','localtime')` | ✅ 无残留 | 该文件原本就不含 SQLite 时间函数 |
| UPDATE 写 updated_at | ✅ | L322: `reorder_goals()` 新增 `updated_at = ?` |
| INSERT 写 created_at | ✅ | L678: `upsert_stats()` 新增 `created_at` |
| 日期字段 | ✅ 正确 | `date` 字段保持 `YYYY-MM-DD`（goal_stats.date 是日期字段） |
| `upsert_stats()` UPDATE 不写 updated_at | ✅ 正确 | L664 注释说明 `goal_stats 无 update_at`，与 `GOAL_STATS_CONFIG` 一致 |

### 1.2 diary_provider.py -- ✅ 通过

| 检查项 | 结果 | 位置/说明 |
|--------|------|-----------|
| `datetime('now','localtime')` | ✅ 已删除 | L156-188: 整个自定义 SQL 块被移除 |
| 委托 `_generic_update` | ✅ 正确 | L161: `_generic_update` 通过 `_TABLES_WITH_UPDATE_AT` 判断，`diary` 配置为 `update_at: True` |
| 代码简化 | ✅ 净减少 ~30 行 | 消除了 `datetime('now','localtime')` 专用路径 |

### 1.3 todo_provider.py -- ✅ 通过

| 检查项 | 结果 | 位置/说明 |
|--------|------|-----------|
| `datetime.now()` 无时区 | ✅ 无调用 | 统一使用 `get_utc_now_iso()` |
| UPDATE 写 updated_at | ✅ | L448: `reorder_todos()`, L516: `reorder_task_pool()`, L753: `_batch_update()`, L820: `_batch_update_waid_order()` |
| INSERT 写 created_at + updated_at | ✅ | L671-672: `_batch_insert()` 新增两列 |
| 格式一致性 | ✅ | 全部使用 `get_utc_now_iso()` → ISO 8601 + UTC |

### 1.4 plan_doc_provider.py -- ✅ 通过

| 检查项 | 结果 | 位置/说明 |
|--------|------|-----------|
| `datetime('now')` → Python 值 | ✅ | L243: `datetime('now')` → `get_utc_now_iso()`, L311: 同上 |
| UPDATE 写 updated_at | ✅ | L244: 参数化绑定 `updated_at = ?` |

### 1.5 habit_providers.py -- ✅ 通过

| 检查项 | 结果 | 位置/说明 |
|--------|------|-----------|
| `datetime.now()` 无时区 | ✅ 已清理 | L403-404: `datetime.now().isoformat()` → `datetime.now(timezone.utc).isoformat()` |
| `strftime()` 残留 | ✅ 已清理 | L404: `strftime("%Y-%m-%d %H:%M:%S")` → `.isoformat()` |
| **两次 `datetime.now(timezone.utc)` 调用** | ⚠️ 微秒差异 | L403-404: `now`（finished_at）和 `updated_at` 分两次调用，值可能差几微秒。语义上 `updated_at` 应 >= `finished_at`，实际成立（因为 `updated_at` 在后），可接受 |

### 1.6 habit_chain_providers.py -- ✅ 通过

| 检查项 | 结果 | 位置/说明 |
|--------|------|-----------|
| `datetime.now()` 无时区 | ✅ 已清理 | L386: `datetime.now(timezone.utc)` |
| `strftime()` 残留 | ✅ 已清理 | L386: `strftime(...)` → `.isoformat()` |
| INSERT 写 created_at + updated_at | ✅ | L99-100: `HabitChainProvider`, L276-277: `HabitChainNodeProvider` |

### 1.7 mood_providers.py -- ✅ 通过

| 检查项 | 结果 | 位置/说明 |
|--------|------|-----------|
| INSERT 写 created_at | ✅ | L496: `MoodImpactProvider._insert()` 新增 `created_at` |
| 未写 updated_at | ✅ 正确 | `mood_impacts` 配置 `update_at: False`，表无该列 |

### 1.8 behavior_analysis_provider.py -- ✅ 通过

| 检查项 | 结果 | 位置/说明 |
|--------|------|-----------|
| 本地日期 → UTC 范围查询 | ✅ | L105, L138, L250: `f"{date} 00:00:00"` → `build_utc_time_range(date)` |
| `datetime('now','localtime')` | ✅ 已删除 | L314: 旧 INSERT 使用 SQLite 函数 → Python `get_utc_now_iso()` |
| INSERT 写 created_at + updated_at | ✅ | L324-325: 新增两列，`behavior_analysis` 配置 `timestamps: True, update_at: True` |

### 1.9 raw_behavior_analysis_provider.py -- ✅ 通过

| 检查项 | 结果 | 位置/说明 |
|--------|------|-----------|
| 本地日期 → UTC 范围查询 | ✅ | L96, L248: `f"{date} 00:00:00"` → `build_utc_time_range(date)` |
| `datetime('now','localtime')` | ✅ 已删除 | L190: 旧 INSERT 使用 SQLite 函数 → Python `get_utc_now_iso()` |
| 未写 updated_at | ✅ 正确 | `raw_behavior_analysis` 配置 `update_at: False`，表无该列 |

### 1.10 custom_block_provider.py -- ✅ 通过

| 检查项 | 结果 | 位置/说明 |
|--------|------|-----------|
| 移除 `.replace("T", " ")` | ✅ | L160-163 和 L195-198: 删除 ISO 8601 T→空格转换。时间字段现在以原生 ISO 8601 格式存储，与 UTC 迁移一致 |

### 1.11 map_cache_providers.py -- ✅ 通过

| 检查项 | 结果 | 位置/说明 |
|--------|------|-----------|
| `datetime.now()` 无时区 | ✅ 已清理 | `MultiPurposeMapCacheProvider.batch_update` L312, `SinglePurposeMapCacheProvider.batch_update` L673 |
| INSERT 写 created_at + updated_at | ✅ | `MultiPurposeMapCacheProvider.batch_insert` L254-258, `SinglePurposeMapCacheProvider.batch_insert` L615-619 |

### 1.12 custom_record_aggregator.py -- ✅ 通过

| 检查项 | 结果 | 位置/说明 |
|--------|------|-----------|
| `strftime()` 残留 | ✅ 已清理 | L126, L381, L601: 3处 `strftime("%Y-%m-%d %H:%M:%S")` → `.isoformat()` |

---

## 2. 潜在 Bug

### 🟡 B-001: map_cache batch_insert 盲追加 created_at/updated_at 列

- **文件**: `map_cache_providers.py`
- **位置**: `MultiPurposeMapCacheProvider.batch_insert` L255-258, `SinglePurposeMapCacheProvider.batch_insert` L616-619
- **代码**:
  ```python
  fields = list(data.keys()) + ["created_at", "updated_at"]
  ```
- **问题**: 如果调用方传入的 `data` 中已包含 `created_at` 或 `updated_at` 键，会导致 SQL 列重复错误。
- **风险评估**: 低。当前调用方不传时间戳字段到 map cache 数据中，但缺乏防御性检查。建议加 `if "created_at" not in data` 保护。
- **严重程度**: 🟡 低风险

### 🟡 B-002: behavior_analysis / raw_behavior_analysis 查询语义变更依赖数据迁移

- **文件**: `behavior_analysis_provider.py` L105, L138, L250; `raw_behavior_analysis_provider.py` L96, L248
- **代码**:
  ```python
  # 旧: start_datetime = f"{date} 00:00:00"  (本地时间字符串)
  # 新: start_datetime, _ = build_utc_time_range(date)  (UTC ISO 8601)
  ```
- **问题**: `build_utc_time_range(date)` 将本地日期转为 UTC 时间范围。查询的 `start_time`/`end_time` 列如果尚未迁移为 UTC ISO 8601 格式（仍是旧的本地时间字符串），将导致查询返回空结果或错误数据。
- **风险评估**: 中。这是迁移顺序依赖——必须确保 `start_time`/`end_time` 数据已迁移为 UTC ISO 8601 格式后，此代码才能正确工作。
- **严重程度**: 🟡 中风险（迁移顺序依赖）

### 🟢 B-003: HabitChallengeProvider 两次 now() 调用

- **文件**: `habit_providers.py`
- **位置**: L403-404
- **代码**:
  ```python
  now = datetime.now(timezone.utc).isoformat()         # finished_at
  updated_at = datetime.now(timezone.utc).isoformat()  # updated_at
  ```
- **评估**: 无实际危害。两个时间戳语义不同（`finished_at` vs `updated_at`），`updated_at` 在 `finished_at` 之后赋值，自然满足 `updated_at >= finished_at`。

---

## 3. 功能缺失风险

**无功能缺失风险**。所有变更均为格式或时区替换，未删除任何时间写入逻辑：

- `diary_provider.py`: 自定义 SQL 路径被 `_generic_update` 替代，`updated_at` 写入能力保留
- `custom_block_provider.py`: `.replace("T", " ")` 被删除但不影响功能——时间字段现以 ISO 8601 原生存储
- 所有 INSERT 路径：新增 `created_at`/`updated_at` 写入，未移除任何原有字段写入
- 所有 UPDATE 路径：新增 `updated_at` 写入，未移除任何原有字段写入

---

## 4. 安全隐患

**无安全隐患**。所有变更为纯数据格式替换，不涉及：
- 用户输入验证变更
- 权限检查变更
- SQL 注入（已使用参数化查询）
- 敏感数据处理

---

## 总结

| 维度 | 评级 | 说明 |
|------|------|------|
| 规则遵守 | ✅ 优秀 | 12 个文件中无 `datetime.now()` 无时区、无 `strftime()`、无 `datetime('now','localtime')` 残留 |
| Bug 风险 | 🟡 低 | 2 个低风险发现：map_cache 盲追加列（需加防御检查）、查询语义依赖迁移顺序 |
| 功能缺失 | 🟢 无 | 未删除任何时间写入逻辑 |
| 安全隐患 | 🟢 无 | 纯数据格式替换 |

**整体评估**: 变更质量高，机械替换准确。`datetime('now')` / `datetime('now','localtime')` → Python `get_utc_now_iso()` 的替换完整且正确。日期字段（如 `date`、`goal_stats.date`）正确处理为本地 `YYYY-MM-DD` 格式。`build_utc_time_range()` 正确地封装了本地日期 → UTC 范围的转换逻辑。

**建议**:
1. 对 map_cache `batch_insert` 增加防御性检查：`if "created_at" not in data` 再追加列
2. 确认 behavior_analysis / raw_behavior_analysis 的 `start_time`/`end_time` 数据迁移在代码部署前完成
