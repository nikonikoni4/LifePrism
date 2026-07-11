# Backend Time Fields Inventory

> **生成时间**: 2026-07-12  
> **目的**: 全面清点后端所有时间相关字段，验证 SQLite CURRENT_TIMESTAMP 行为，分析之前报告的覆盖度

---

## 第一部分：时间字段完整清单

### 1. SQLite 自动生成的时间字段（TIMESTAMP DEFAULT）

| 表名 | 字段名 | 数据类型 | DEFAULT 子句 | 是否同步 | 代码写入位置 | 备注 |
|------|--------|----------|--------------|----------|--------------|------|
| category_map_cache | created_at | TIMESTAMP | `datetime('now', 'localtime')` | ✅ 是 | 自动 | timestamps=True |
| category_map_cache | updated_at | TIMESTAMP | `datetime('now', 'localtime')` | ✅ 是 | 自动/手动 | update_at=True |
| multi_purpose_map_cache | created_at | TIMESTAMP | `datetime('now', 'localtime')` | ✅ 是 | 自动 | timestamps=True |
| multi_purpose_map_cache | updated_at | TIMESTAMP | `datetime('now', 'localtime')` | ✅ 是 | 自动/手动 | update_at=True |
| single_purpose_map_cache | created_at | TIMESTAMP | `datetime('now', 'localtime')` | ✅ 是 | 自动 | timestamps=True |
| single_purpose_map_cache | updated_at | TIMESTAMP | `datetime('now', 'localtime')` | ✅ 是 | 自动/手动 | update_at=True |
| user_app_behavior_log | created_at | TIMESTAMP | `datetime('now', 'localtime')` | ✅ 是 | 自动 | timestamps=True |
| user_app_behavior_log | updated_at | TIMESTAMP | `datetime('now', 'localtime')` | ✅ 是 | 自动/手动 | update_at=True |
| category | created_at | TIMESTAMP | `datetime('now', 'localtime')` | ✅ 是 | 自动 | timestamps=True |
| category | updated_at | TIMESTAMP | `datetime('now', 'localtime')` | ✅ 是 | 自动/手动 | update_at=True |
| sub_category | created_at | TIMESTAMP | `datetime('now', 'localtime')` | ✅ 是 | 自动 | timestamps=True |
| sub_category | updated_at | TIMESTAMP | `datetime('now', 'localtime')` | ✅ 是 | 自动/手动 | update_at=True |
| tokens_usage_log | created_at | TIMESTAMP | `datetime('now', 'localtime')` | ❌ 否 | 自动 | timestamps=True, 无 updated_at |
| todo_list | created_at | TEXT | CURRENT_TIMESTAMP | ✅ 是 | 自动 | ⚠️ 旧迁移遗留 |
| todo_list | updated_at | TIMESTAMP | NULL | ✅ 是 | 手动 | ⚠️ 无 DEFAULT |
| daily_focus | created_at | TIMESTAMP | `datetime('now', 'localtime')` | ✅ 是 | 自动 | timestamps=True |
| daily_focus | updated_at | TIMESTAMP | `datetime('now', 'localtime')` | ✅ 是 | 自动/手动 | update_at=True |
| weekly_focus | created_at | TIMESTAMP | `datetime('now', 'localtime')` | ✅ 是 | 自动 | timestamps=True |
| weekly_focus | updated_at | TIMESTAMP | `datetime('now', 'localtime')` | ✅ 是 | 自动/手动 | update_at=True |
| goal | created_at | TIMESTAMP | `datetime('now', 'localtime')` | ✅ 是 | 自动 | timestamps=True |
| goal | updated_at | TIMESTAMP | `datetime('now', 'localtime')` | ✅ 是 | 自动/手动 | update_at=True |
| goal_journal | created_at | TIMESTAMP | `datetime('now', 'localtime')` | ✅ 是 | 自动 | timestamps=True |
| goal_journal | updated_at | TIMESTAMP | `datetime('now', 'localtime')` | ✅ 是 | 自动/手动 | update_at=True |
| plan_doc | created_at | TIMESTAMP | `datetime('now', 'localtime')` | ✅ 是 | 自动 | timestamps=True |
| plan_doc | updated_at | TIMESTAMP | `datetime('now', 'localtime')` | ✅ 是 | 自动/手动 | update_at=True |
| chat_session | created_at | TEXT | 无 | ❌ 否 | 手动 | timestamps=False |
| chat_session | updated_at | TEXT | 无 | ❌ 否 | 手动 | timestamps=False |
| timeline_custom_block | created_at | TEXT | CURRENT_TIMESTAMP | ✅ 是 | 自动 | ⚠️ 旧迁移遗留 |
| timeline_custom_block | updated_at | TEXT | CURRENT_TIMESTAMP | ✅ 是 | 自动/手动 | ⚠️ 旧迁移遗留 |
| goal_stats | created_at | TIMESTAMP | `datetime('now', 'localtime')` | ❌ 否 | 自动 | timestamps=True, 无 updated_at |
| daily_report | created_at | TIMESTAMP | `datetime('now', 'localtime')` | ✅ 是 | 自动 | timestamps=True |
| daily_report | updated_at | TIMESTAMP | `datetime('now', 'localtime')` | ✅ 是 | 自动/手动 | update_at=True |
| weekly_report | created_at | TIMESTAMP | `datetime('now', 'localtime')` | ✅ 是 | 自动 | timestamps=True |
| weekly_report | updated_at | TIMESTAMP | `datetime('now', 'localtime')` | ✅ 是 | 自动/手动 | update_at=True |
| monthly_report | created_at | TIMESTAMP | `datetime('now', 'localtime')` | ✅ 是 | 自动 | timestamps=True |
| monthly_report | updated_at | TIMESTAMP | `datetime('now', 'localtime')` | ✅ 是 | 自动/手动 | update_at=True |
| time_paradoxes | created_at | TIMESTAMP | `datetime('now', 'localtime')` | ✅ 是 | 自动 | timestamps=True |
| time_paradoxes | updated_at | TIMESTAMP | `datetime('now', 'localtime')` | ✅ 是 | 自动/手动 | update_at=True |
| diary | created_at | TIMESTAMP | `datetime('now', 'localtime')` | ✅ 是 | 自动 | timestamps=True |
| diary | updated_at | TIMESTAMP | `datetime('now', 'localtime')` | ✅ 是 | 自动/手动 | update_at=True |
| mood_types | created_at | TIMESTAMP | `datetime('now', 'localtime')` | ❌ 否 | 自动 | timestamps=True, update_at=False |
| mood_entries | created_at | TIMESTAMP | `datetime('now', 'localtime')` | ✅ 是 | 自动 | timestamps=True |
| mood_entries | updated_at | TIMESTAMP | `datetime('now', 'localtime')` | ✅ 是 | 自动/手动 | update_at=True |
| mood_impacts | created_at | TIMESTAMP | `datetime('now', 'localtime')` | ❌ 否 | 自动 | timestamps=True, update_at=False |
| user_values | created_at | TIMESTAMP | `datetime('now', 'localtime')` | ✅ 是 | 自动 | timestamps=True |
| user_values | updated_at | TIMESTAMP | `datetime('now', 'localtime')` | ✅ 是 | 自动/手动 | update_at=True |
| commitments | created_at | TIMESTAMP | `datetime('now', 'localtime')` | ✅ 是 | 自动 | timestamps=True |
| commitments | updated_at | TIMESTAMP | `datetime('now', 'localtime')` | ✅ 是 | 自动/手动 | update_at=True |
| schema_version | applied_at | TIMESTAMP | `datetime('now', 'localtime')` | ❌ 否 | 自动 | 特殊：迁移版本表 |
| habits | created_at | TIMESTAMP | `datetime('now', 'localtime')` | ✅ 是 | 自动 | timestamps=True |
| habits | updated_at | TIMESTAMP | `datetime('now', 'localtime')` | ✅ 是 | 自动/手动 | update_at=True |
| habit_challenges | created_at | TIMESTAMP | `datetime('now', 'localtime')` | ✅ 是 | 自动 | timestamps=True |
| habit_challenges | updated_at | TIMESTAMP | `datetime('now', 'localtime')` | ✅ 是 | 自动/手动 | update_at=True |
| habit_checkins | created_at | TIMESTAMP | `datetime('now', 'localtime')` | ✅ 是 | 自动 | timestamps=True, update_at=False |
| habit_chains | created_at | TIMESTAMP | `datetime('now', 'localtime')` | ✅ 是 | 自动 | timestamps=True |
| habit_chains | updated_at | TIMESTAMP | `datetime('now', 'localtime')` | ✅ 是 | 自动/手动 | update_at=True |
| habit_chain_nodes | created_at | TIMESTAMP | `datetime('now', 'localtime')` | ✅ 是 | 自动 | timestamps=True |
| habit_chain_nodes | updated_at | TIMESTAMP | `datetime('now', 'localtime')` | ✅ 是 | 自动/手动 | update_at=True |
| screen_captures | created_at | TIMESTAMP | `datetime('now', 'localtime')` | ✅ 是 | 自动 | timestamps=True, update_at=False |
| window_events | created_at | TIMESTAMP | `datetime('now', 'localtime')` | ❌ 否 | 自动 | timestamps=True, update_at=False |
| raw_behavior_analysis | created_at | TIMESTAMP | `datetime('now', 'localtime')` | ❌ 否 | 自动 | timestamps=True, update_at=False |
| behavior_analysis | created_at | TIMESTAMP | `datetime('now', 'localtime')` | ✅ 是 | 自动 | timestamps=True |
| behavior_analysis | updated_at | TIMESTAMP | `datetime('now', 'localtime')` | ✅ 是 | 自动/手动 | update_at=True |
| custom_record_types | created_at | TIMESTAMP | `datetime('now', 'localtime')` | ✅ 是 | 自动 | timestamps=True |
| custom_record_types | updated_at | TIMESTAMP | `datetime('now', 'localtime')` | ✅ 是 | 自动/手动 | update_at=True |
| custom_record_fields | created_at | TIMESTAMP | `datetime('now', 'localtime')` | ✅ 是 | 自动 | timestamps=True, update_at=False |

### 2. 业务时间字段（非自动生成）

| 表名 | 字段名 | 数据类型 | DEFAULT 子句 | 是否同步 | 代码写入位置 | 备注 |
|------|--------|----------|--------------|----------|--------------|------|
| user_app_behavior_log | start_time | TEXT | NOT NULL | ✅ 是 | 代码写入 | 行为开始时间 |
| user_app_behavior_log | end_time | TEXT | NOT NULL | ✅ 是 | 代码写入 | 行为结束时间 |
| todo_list | date | TEXT | NULL | ✅ 是 | 代码写入 | YYYY-MM-DD |
| todo_list | expected_finished_at | TEXT | NULL | ✅ 是 | 代码写入 | YYYY-MM-DD |
| todo_list | actual_finished_at | TEXT | NULL | ✅ 是 | 代码写入 | YYYY-MM-DD |
| daily_focus | date | TEXT | NOT NULL | ✅ 是 | 代码写入 | YYYY-MM-DD |
| weekly_focus | year | INTEGER | NOT NULL | ✅ 是 | 代码写入 | 年份 |
| weekly_focus | month | INTEGER | NOT NULL | ✅ 是 | 代码写入 | 月份 |
| weekly_focus | week_num | INTEGER | NOT NULL | ✅ 是 | 代码写入 | 周序号 |
| goal | start_date | TEXT | NULL | ✅ 是 | 代码写入 | YYYY-MM-DD |
| goal | expected_finished_at | TEXT | NULL | ✅ 是 | 代码写入 | YYYY-MM-DD |
| goal | time_invested_updated_at | TEXT | NULL | ✅ 是 | 代码写入 | ISO 8601 |
| goal_journal | date | TEXT | NOT NULL | ✅ 是 | 代码写入 | YYYY-MM-DD |
| goal_journal | time | TEXT | NULL | ✅ 是 | 代码写入 | HH:MM |
| goal_stats | date | TEXT | NOT NULL | ❌ 否 | 代码写入 | YYYY-MM-DD |
| daily_report | date | TEXT | PRIMARY KEY | ✅ 是 | 代码写入 | YYYY-MM-DD |
| weekly_report | date | TEXT | PRIMARY KEY | ✅ 是 | 代码写入 | YYYY-MM-DD |
| monthly_report | date | TEXT | PRIMARY KEY | ✅ 是 | 代码写入 | YYYY-MM-DD |
| diary | date | TEXT | PRIMARY KEY | ✅ 是 | 代码写入 | YYYY-MM-DD |
| timeline_custom_block | start_time | TEXT | NOT NULL | ✅ 是 | 代码写入 | ISO 格式 |
| timeline_custom_block | end_time | TEXT | NOT NULL | ✅ 是 | 代码写入 | ISO 格式 |
| habits | paused_at | TEXT | NULL | ✅ 是 | 代码写入 | 暂停时间 |
| habit_challenges | start_date | TEXT | NOT NULL | ✅ 是 | 代码写入 | YYYY-MM-DD |
| habit_challenges | end_date | TEXT | NOT NULL | ✅ 是 | 代码写入 | YYYY-MM-DD |
| habit_challenges | finished_at | TEXT | NULL | ✅ 是 | 代码写入 | 结束时间 |
| habit_checkins | date | TEXT | NOT NULL | ✅ 是 | 代码写入 | YYYY-MM-DD |
| habit_checkins | completed_at | TEXT | NULL | ✅ 是 | 代码写入 | 实际完成时间戳 |
| habit_chain_nodes | trigger_time | TEXT | NULL | ✅ 是 | 代码写入 | HH:mm |
| screen_captures | captured_at | TEXT | NOT NULL | ✅ 是 | 代码写入 | ISO 格式 |
| window_events | timestamp | TEXT | NOT NULL | ❌ 否 | 代码写入 | ISO 格式 |
| raw_behavior_analysis | start_time | TEXT | PRIMARY KEY | ❌ 否 | 代码写入 | YYYY-MM-DD HH:MM:SS |
| raw_behavior_analysis | end_time | TEXT | NOT NULL | ❌ 否 | 代码写入 | YYYY-MM-DD HH:MM:SS |
| behavior_analysis | start_time | TEXT | PRIMARY KEY | ✅ 是 | 代码写入 | YYYY-MM-DD HH:MM:SS |
| behavior_analysis | end_time | TEXT | NOT NULL | ✅ 是 | 代码写入 | YYYY-MM-DD HH:MM:SS |

---

## 第二部分：SQLite 自动生成行为

### 2.1 SQLite CURRENT_TIMESTAMP 行为验证

**测试结果**（2026-07-12 00:29:54 本地时间）：

```sql
SELECT datetime('now'), datetime('now', 'localtime')
```

**输出**：
```
2026-07-11 16:29:54 | 2026-07-12 00:29:54
```

**结论**：
- `datetime('now')` 返回 **UTC 时间**（2026-07-11 16:29:54）
- `datetime('now', 'localtime')` 返回 **本地时间**（2026-07-12 00:29:54，UTC+8）
- 格式为 `YYYY-MM-DD HH:MM:SS`（**不带 T**，空格分隔）
- **不包含时区信息**

### 2.2 代码中的时间生成行为

#### SQLite 表定义（`lw_table_manager.py`）

```python
# 第 81-85 行
if timestamps:
    column_definitions.append("created_at TIMESTAMP DEFAULT (datetime('now', 'localtime'))")
    if update_at:
        column_definitions.append("updated_at TIMESTAMP DEFAULT (datetime('now', 'localtime'))")
```

**行为**：
- 所有 `timestamps=True` 的表使用 `datetime('now', 'localtime')` 生成 **本地时间**
- 格式：`YYYY-MM-DD HH:MM:SS`（不带 T）

#### Python 代码写入时间（`datetime.now().isoformat()`）

**位置**：`lifeprism/repository/base_providers/lw_base_data_provider.py:1184`

```python
data["updated_at"] = datetime.now().isoformat()
```

**行为**：
- `datetime.now()` 返回本地时间
- `.isoformat()` 格式为 `YYYY-MM-DDTHH:MM:SS.ffffff`（**带 T**）

#### 格式不一致问题

| 来源 | 格式 | 示例 |
|------|------|------|
| SQLite DEFAULT | `YYYY-MM-DD HH:MM:SS` | `2026-07-12 00:29:54` |
| Python `.isoformat()` | `YYYY-MM-DDTHH:MM:SS.ffffff` | `2026-07-12T00:29:54.123456` |
| Python `.strftime()` | `YYYY-MM-DD HH:MM:SS` | `2026-07-12 00:29:54` |

**⚠️ 潜在问题**：
1. **格式不一致**：SQLite 默认无 T，Python `.isoformat()` 有 T
2. **精度不一致**：SQLite 秒级，Python 微秒级
3. **同步冲突风险**：云端可能因格式不一致判断为"需要更新"

---

## 第三部分：之前报告的覆盖度分析

### 3.1 之前报告遗漏的字段

**假设之前报告只检查了 `updated_at` 字段**，以下字段被遗漏：

#### 完全遗漏的时间字段类型：

1. **created_at 字段**（48 个表有此字段，但可能未被检查）
2. **业务时间字段**（35 个字段）：
   - `start_time`, `end_time`（user_app_behavior_log, timeline_custom_block, raw_behavior_analysis, behavior_analysis）
   - `date`（todo_list, daily_focus, goal_journal, goal_stats, daily_report, weekly_report, monthly_report, diary, habit_checkins）
   - `expected_finished_at`, `actual_finished_at`（todo_list, goal）
   - `start_date`, `end_date`（goal, habit_challenges）
   - `time`（goal_journal）
   - `year`, `month`, `week_num`（weekly_focus）
   - `time_invested_updated_at`（goal）
   - `paused_at`, `finished_at`（habits, habit_challenges）
   - `completed_at`（habit_checkins）
   - `trigger_time`（habit_chain_nodes）
   - `captured_at`（screen_captures）
   - `timestamp`（window_events）
   - `applied_at`（schema_version）

3. **特殊字段**：
   - `chat_session.created_at / updated_at`（类型为 TEXT，手动写入，timestamps=False）
   - `todo_list.created_at`（类型为 TEXT，DEFAULT CURRENT_TIMESTAMP，迁移遗留）
   - `timeline_custom_block.created_at / updated_at`（类型为 TEXT，DEFAULT CURRENT_TIMESTAMP，迁移遗留）

### 3.2 需要补充调查的字段

#### 高优先级（参与数据同步）

以下字段参与数据同步，必须检查格式一致性：

1. **自动生成的 updated_at**（35 个表）
2. **自动生成的 created_at**（48 个表）
3. **业务时间字段**（29 个字段，标注"是否同步=是"）

#### 中优先级（不同步但影响显示）

1. `goal_stats.date`：不同步，但前端展示需要
2. `window_events.timestamp`：不同步，但影响行为分析
3. `raw_behavior_analysis.start_time / end_time`：不同步，但被 behavior_analysis 引用

#### 低优先级（内部使用）

1. `schema_version.applied_at`：迁移记录，不对外暴露
2. `mood_types.created_at`：配置表，update_at=False
3. `mood_impacts.created_at`：配置表，update_at=False

### 3.3 关键发现

#### 🔴 旧迁移遗留问题

以下表使用了 **CURRENT_TIMESTAMP** 而非 `datetime('now', 'localtime')`：

1. `todo_list.created_at`（TEXT DEFAULT CURRENT_TIMESTAMP）
2. `timeline_custom_block.created_at`（TEXT DEFAULT CURRENT_TIMESTAMP）
3. `timeline_custom_block.updated_at`（TEXT DEFAULT CURRENT_TIMESTAMP）

**问题**：
- `CURRENT_TIMESTAMP` 生成 **UTC 时间**（如 `2026-07-11 16:29:54`）
- 其他表使用 `datetime('now', 'localtime')` 生成本地时间（如 `2026-07-12 00:29:54`）
- **时区不一致**可能导致数据同步错误

#### 🟡 Python 代码写入格式不一致

**位置**：
- `lw_base_data_provider.py:1184`: `datetime.now().isoformat()`（带 T）
- `habit_providers.py:403`: `datetime.now().isoformat()`（带 T）
- `habit_providers.py:404`: `datetime.now().strftime("%Y-%m-%d %H:%M:%S")`（不带 T）
- `map_cache_providers.py:311, 672`: `datetime.now().isoformat()`（带 T）

**问题**：
- 部分代码使用 `.isoformat()`（带 T），部分使用 `.strftime()`（不带 T）
- 与 SQLite DEFAULT 格式不一致

---

## 第四部分：修复建议

### 4.1 立即修复（高优先级）

1. **修复旧迁移遗留**：
   - 迁移 `todo_list.created_at` 从 `CURRENT_TIMESTAMP` 改为 `datetime('now', 'localtime')`
   - 迁移 `timeline_custom_block.created_at / updated_at` 从 `CURRENT_TIMESTAMP` 改为 `datetime('now', 'localtime')`
   - 历史数据需要时区转换（UTC → 本地时间）

2. **统一 Python 代码写入格式**：
   - 所有 `datetime.now().isoformat()` 改为 `datetime.now().strftime("%Y-%m-%d %H:%M:%S")`
   - 或在 `lw_base_data_provider.py` 中封装统一方法

### 4.2 中期优化（中优先级）

1. **验证数据同步逻辑**：
   - 检查云端是否因格式不一致判断为"需要更新"
   - 测试 `2026-07-12 00:29:54` vs `2026-07-12T00:29:54.123456` 的同步行为

2. **统一时间字段类型**：
   - `chat_session.created_at / updated_at` 改为 TIMESTAMP 类型
   - 考虑是否将所有业务时间字段改为 TIMESTAMP（影响较大）

### 4.3 长期改进（低优先级）

1. **引入时区感知**：
   - 考虑使用 `datetime.now(timezone.utc)` 存储 UTC 时间
   - 前端显示时转换为本地时间

2. **文档化时间字段规范**：
   - 在 `docs/coding-rules/` 中添加时间字段处理规则
   - 明确何时使用 SQLite DEFAULT，何时使用 Python 写入

---

## 附录：统计汇总

### 字段数量统计

| 分类 | 数量 |
|------|------|
| **自动生成的 created_at** | 48 个表 |
| **自动生成的 updated_at** | 35 个表（部分表 update_at=False） |
| **业务时间字段** | 35 个字段 |
| **参与数据同步的时间字段** | ~70 个字段 |
| **使用 CURRENT_TIMESTAMP 的表** | 3 个（旧迁移遗留） |

### 表分类统计

| 分类 | 数量 | 备注 |
|------|------|------|
| **有 created_at + updated_at** | 32 个表 | 标准同步表 |
| **仅有 created_at** | 7 个表 | update_at=False |
| **手动管理时间戳** | 2 个表 | chat_session, schema_version |
| **使用旧格式** | 2 个表 | todo_list, timeline_custom_block |

---

## 结论

1. **SQLite CURRENT_TIMESTAMP 行为**：
   - `datetime('now')` → UTC 时间
   - `datetime('now', 'localtime')` → 本地时间（UTC+8）
   - 格式：`YYYY-MM-DD HH:MM:SS`（不带 T）

2. **之前报告覆盖度**：
   - 如果只检查了 `updated_at`，则遗漏了 `created_at`（48 个表）和业务时间字段（35 个字段）
   - 需要补充检查所有参与同步的时间字段（约 70 个）

3. **关键问题**：
   - 🔴 旧迁移遗留：3 个表使用 `CURRENT_TIMESTAMP`（UTC 时间）
   - 🟡 Python 代码格式不一致：部分使用 `.isoformat()`（带 T），部分使用 `.strftime()`（不带 T）
   - 🟡 潜在同步冲突：格式不一致可能导致云端误判"需要更新"

4. **修复优先级**：
   - **立即**：修复旧迁移遗留，统一 Python 写入格式
   - **中期**：验证同步逻辑，统一时间字段类型
   - **长期**：引入时区感知，文档化规范
