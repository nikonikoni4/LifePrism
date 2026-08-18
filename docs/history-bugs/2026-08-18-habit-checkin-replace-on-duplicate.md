---
version: 1.0
created_at: 2026-08-18
updated_at: 2026-08-18
last_updated: 创建文档初稿，记录 habit_checkins 重复打卡被静默替换的 bug
abstract: habit_providers.create_checkin 使用默认 on_conflict='replace' 策略，UNIQUE(habit_id, date) 冲突时静默替换当天已有记录，导致同一天重复打卡被计入 2 次完成数而非报错
---

# habit_checkins 重复打卡被静默替换

## Bug 简述

同一习惯同一天重复打卡时，第二次打卡不报 `CHECKIN_ALREADY_EXISTS` 错误，而是静默成功：`completed_count` 被累加 2 次，且当天打卡记录被替换为新记录（id 和 hash_id 均变化）。违反 habit-system spec 边界条件验收"同一天重复打卡应报错"。

## 复用场景

- 其他依赖 `_ON_CONFLICT` 默认值 `'replace'` 且期望"业务唯一键冲突时报错"的 provider 方法
- 新增带业务 UNIQUE 约束的插入方法时，`replace`/`ignore`/`abort` 三种策略的选择判断
- 同步场景（upsert_rows LWW）需要 `replace`，业务插入场景需要 `ignore`+None 返回值，两者不可混淆

## 代码位置

- `lifeprism/repository/providers/habit_providers.py` - `HabitCheckinProvider.create_checkin`（修复点）
- `lifeprism/repository/base_providers/lw_base_data_provider.py:64` - `_ON_CONFLICT: str = "replace"` 默认值
- `lifeprism/config/database.py` - `HABIT_CHECKINS_CONFIG.table_constraints` 中的 `UNIQUE(habit_id, date)`

## 发生原因

`create_checkin` 调用 `self._generic_insert(insert_data)` 时未指定 `on_conflict`，落入基类默认策略 `'replace'`（该默认值为同步场景的 `INSERT OR REPLACE` LWW 设计）。重复打卡触发 `UNIQUE(habit_id, date)` 冲突时，SQLite 执行 REPLACE：删除旧行、插入新行（新 id + 新 hash_id），语句正常返回不抛 `sqlite3.IntegrityError`。因此：

1. 函数注释中"IntegrityError -> return None"的防御分支永远不会命中
2. service 层拿到新 id 认为打卡成功，`completed_count` +1（当天实际被计 2 次）
3. 被替换记录的旧 hash_id 无墓碑消失，对同步层产生"旧记录消失 + 新记录新增"的噪音

## 最佳方案

显式指定冲突策略并利用 `ignore` 模式的 rowcount 语义：

```python
result = self._generic_insert(insert_data, on_conflict="ignore")
if result is None:
    return None  # 重复打卡，service 层抛 ConflictError
```

`_generic_insert` 在 `ignore` 模式下检测 `cursor.rowcount == 0` 返回 None，由 `create_checkin` 透传 None，`habit_service.checkin_today` / `backfill_checkin` 据此抛 `ConflictError("今日已打卡")`。

回归测试：`test/core/integration/llm/agent/tools/test_habit_tool.py::TestCheckinHabitTool::test_checkin_duplicate`（先写复现测试后修复，修复前该测试失败、修复后通过）。

**教训**：`_ON_CONFLICT` 默认 `'replace'` 是为同步 LWW 设计的；业务层插入方法若依赖 UNIQUE 约束做幂等/去重判定，必须显式传 `on_conflict="ignore"` 或 `"abort"`，并依赖返回值/异常区分冲突，不能假设 IntegrityError 会抛出。
