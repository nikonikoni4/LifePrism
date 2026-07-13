# Mood Entries / Custom Records 日期查询问题 & 自定义数据表 UTC 迁移遗漏

## 元信息

本文件记录了三类相关但性质不同的已知问题：

| 问题 | 类型 | 严重程度 |
|------|------|---------|
| 自定义数据表 UTC 迁移遗漏 | **数据一致性问题** | ✅ 已修复（2026-07-13） |
| Mood Entries 缺少独立日期字段 | 表设计限制 | ✅ 已修复（2026-07-13），新增 `event_time` + 组件内 UTC 转换 |
| Custom Records 缺少独立日期字段 | 表设计限制 | ✅ 已修复（2026-07-13），新增 `event_time` + 组件内 UTC 转换 |

- **发现时间**: 2026-07-13
- **状态**: 所有问题已修复

## 问题描述

### 1. 自定义数据表迁移缺失（UTC 迁移遗漏）✅ 已修复

**修复**：m009 迁移末尾新增 `_migrate_custom_data_tables()` 函数，遍历 `custom_record_types.slug` 对每个 `custom_<slug>` 表执行 `created_at` / `updated_at` 的 UTC 转换。

**背景**：m009 迁移脚本（[m009_migrate_history_to_utc.py](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/repository/migrations/scripts/m009_migrate_history_to_utc.py)）负责将历史数据从本地时区 (UTC+8) 减 8 小时转为 UTC。该迁移只处理 `TABLE_CONFIGS` 中**静态注册**的表。

**问题**：

- 自定义记录的数据表是**运行时动态创建**的，表名由 `custom_record_types.slug` 决定，格式为 `custom_<slug>`（如 `custom_sport`、`custom_reading`）
- 这些动态表不在 `TABLE_CONFIGS` 中注册，因此 m009 的迁移列表**没有包含它们**
- 结果：`custom_record_types` 和 `custom_record_fields` 的 `created_at` 得到了迁移，但动态数据表 `custom_<slug>` 中的 `created_at` 和 `updated_at` **仍然是本地时区**，没有转换为 UTC

**动态表结构示例**：

```sql
-- custom_record_types 表（元数据，已迁移 ✅）
CREATE TABLE custom_record_types (
    id TEXT PRIMARY KEY NOT NULL,
    name TEXT NOT NULL,
    slug TEXT NOT NULL UNIQUE,   -- 如 "sport", "reading"
    ...
    created_at TEXT,   -- UTC ✅
    updated_at TEXT    -- UTC ✅
);

-- custom_sport 表（动态数据，未迁移 ❌）
CREATE TABLE custom_sport (
    id TEXT PRIMARY KEY NOT NULL,
    distance TEXT,
    duration TEXT,
    ...
    created_at TEXT,   -- 本地时区 ❌
    updated_at TEXT    -- 本地时区 ❌
);
```

**m009 迁移当前覆盖情况**：

| 表 | 迁移状态 |
|----|---------|
| `custom_record_types` (created_at, updated_at) | ✅ 已迁移 |
| `custom_record_fields` (created_at) | ✅ 已迁移 |
| `custom_<slug>` 动态表 (created_at, updated_at) | ❌ **未迁移** |

**正确做法**：迁移时应：

1. 从 `custom_record_types` 读取所有 `slug`
2. 动态组成表名 `custom_<slug>`
3. 对每个动态表执行 `created_at` 和 `updated_at` 的 UTC 转换（减 8 小时）

```python
# 伪代码：正确的迁移逻辑
cursor.execute("SELECT slug FROM custom_record_types")
for row in cursor.fetchall():
    table_name = f"custom_{row['slug']}"
    # 检查表是否存在
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,)
    )
    if cursor.fetchone():
        # 迁移 created_at
        cursor.execute(f'''
            UPDATE "{table_name}"
            SET "created_at" = strftime('%Y-%m-%dT%H:%M:%f',
                datetime("created_at", '-8 hours')) || '+00:00'
            WHERE "created_at" IS NOT NULL AND "created_at" != ''
        ''')
        # 迁移 updated_at
        cursor.execute(f'''
            UPDATE "{table_name}"
            SET "updated_at" = strftime('%Y-%m-%dT%H:%M:%f',
                datetime("updated_at", '-8 hours')) || '+00:00'
            WHERE "updated_at" IS NOT NULL AND "updated_at" != ''
        ''')
```

### 2. Mood Entries API（✅ 已修复）

**原问题**：
- 表中只有 `created_at` datetime 字段（UTC）
- **没有独立的 `date` 字段**用于快速按日期查询
- 每次查询都需要在后端将日期范围转换为 UTC 时间范围
- 无法在数据库层建立基于日期的索引

**修复方案**：
1. 新增系统级 `event_time` 字段（UTC ISO 8601），由 Agent 以本地 `YYYY-MM-DD HH:MM:SS` 提供，execute 层 `local_to_utc_iso()` 转 UTC 存储
2. 查询改用 `WHERE event_time >= ? AND event_time < ?` 替代 `WHERE created_at`
3. 前端 moodTransform.ts 使用 `entry.event_time` 构建 `timestamp`（兼容降级到 `created_at`）
4. LLM Tool Query 工具已有 `local_to_utc_iso()` 转换；Create 工具新增 `event_time` 参数 + 格式校验
5. API 查询参数从 `start_date`/`end_date` 改为 `start_time`/`end_time`（UTC ISO 8601）

**m011 迁移**：`ALTER TABLE mood_entries ADD COLUMN event_time TEXT` + `UPDATE SET event_time = created_at` 回填

### 3. Custom Records API（✅ 已修复）

**原问题**：
- 表中只有 `created_at/updated_at` datetime 字段
- 前端直接传 YYYY-MM-DD → 后端直接做 `created_at >= 'YYYY-MM-DD'` 字符串比较
- 字符串比较逻辑与 UTC ISO 格式不兼容，导致查询结果不正确

**修复方案**：
1. 新增系统级 `event_time` 字段（UTC ISO 8601），由 Agent 以本地 `YYYY-MM-DD HH:MM:SS` 提供，execute 层 `local_to_utc_iso()` 转 UTC 存储
2. 查询改用 `WHERE event_time >= ? AND event_time <= ?` 替代 `WHERE created_at`
3. 前端 TypeDetailView 组件内 `toISOStringUTC()` 将日期转为 UTC 时间范围，遵循就近原则
4. LLM Tool Query 工具 `date_range` 在 execute 层通过 `build_utc_time_range()` 转 UTC

**m010 迁移**：为已有动态表 `ALTER TABLE ADD COLUMN event_time TEXT` + `UPDATE SET event_time = created_at` 回填

## 当前实现

### 后端处理逻辑

Mood 和 Custom Records 均已修复，使用 `event_time` 字段替代 `created_at` 进行查询：

```python
# mood_service.py / custom_records_service.py
def get_entries(start_time: str | None, end_time: str | None):
    # start_time / end_time 已是 UTC ISO 8601（由前端组件或 LLM execute 层转换）
    results = repository.query_by_time_range(start_time, end_time)
    return results
```

### 查询流程

1. **前端**：组件内 `toISOStringUTC()` 将日期转为 UTC 时间范围，传 `start_time`/`end_time`（UTC ISO）
2. **Service 层**：直接透传 UTC ISO 参数
3. **Repository 层**：`WHERE event_time >= ? AND event_time < ?`
4. **LLM Tool execute 层**：`local_to_utc_iso()` 将 Agent 的本地时间转 UTC ISO

## 为什么曾经是"已知限制"

### 三类问题的性质对比

| 对比项 | 自定义表迁移遗漏 | Timeline Custom Block | Mood/Custom Records |
|--------|-----------------|----------------------|---------------------|
| 问题性质 | **数据一致性 bug** | 代码 bug | 表设计限制 → ✅ 已修复 |
| 表结构 | 动态表 `custom_<slug>` | `timeline_custom_block` | `mood_entries` / `custom_<slug>` |
| API 参数 | 无（迁移脚本内部） | 传日期 `date=2026-07-13` | 传时间范围 `start_time/end_time`（UTC ISO） |
| 后端处理 | ✅ m009 已补全迁移 | ✅ 已修复 | ✅ 使用 `event_time` 查询 |
| 数据后果 | ✅ 已修复 | ✅ 已修复 | ✅ 已修复 |

### 性质判定

- **自定义表迁移遗漏** 是 **数据一致性 bug**：m009 迁移脚本遗漏了动态表 `custom_<slug>`，导致自定义记录的时间比实际 UTC 时间早 8 小时。已修复。

- **Timeline Custom Block** 是 **代码 bug**：查询逻辑错误导致查询失败。已修复。

- **Mood/Custom Records** 是 **表设计限制**：缺少独立事件时间字段。已通过新增 `event_time` 字段修复。

## 影响

### 自定义表迁移遗漏（严重）

1. **时间偏差 8 小时**：
   - 动态表 `custom_<slug>` 中的 `created_at` 和 `updated_at` 仍为本地时区 (UTC+8)
   - 新写入的数据使用 `datetime('now')`（UTC），与旧数据时区不一致
   - 新旧数据混合查询时时间比较可能出错

2. **功能影响**：
   - 自定义记录列表中显示的时间会偏差 8 小时
   - 按时间排序时，新旧数据可能交错

### Mood Entries / Custom Records 性能影响（已修复）

1. **event_time 索引**：
   - `event_time` 字段已有索引（`idx_mood_entries_event_time`）
   - 查询效率与日期字段相当

2. **时区转换**：
   - 前端组件内 `toISOStringUTC()` 就近转换
   - LLM Tool execute 层 `local_to_utc_iso()` 转换
   - Repository 层接收纯 UTC ISO，无需转换

3. **聚合统计**：
   - 前端使用 `new Date(entry.event_time)` 获取本地日期进行分组

## 理想设计

### 对比其他表

系统中有独立日期字段的表：

```sql
-- todo_list（正确设计）
CREATE TABLE todo_list (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT,        -- YYYY-MM-DD（本地日期）
    created_at TEXT,  -- UTC ISO 8601
    updated_at TEXT
);

-- diary（正确设计）
CREATE TABLE diary (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT,        -- YYYY-MM-DD（本地日期）
    created_at TEXT,
    updated_at TEXT
);
```

### 理想的 Mood Entries 表

```sql
CREATE TABLE mood_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT,        -- 新增：YYYY-MM-DD（本地日期）
    mood_level INTEGER,
    note TEXT,
    created_at TEXT,  -- UTC ISO 8601
    updated_at TEXT,
    
    INDEX idx_mood_date (date)  -- 日期索引
);
```

**优势**：
- 前端查询：`GET /mood/entries?date=2026-07-13`（直接传日期）
- 后端查询：`WHERE date = ?`（简单高效）
- 聚合统计：`GROUP BY date`（数据库层完成）

## 修复方案（未实施）

### 方案 A：添加 `date` 字段（推荐）

**步骤**：
1. 数据库迁移：添加 `date` 字段
2. 从 `created_at` 提取日期填充 `date`（考虑时区）
3. 修改插入逻辑：同时写入 `date` 和 `created_at`
4. 修改查询逻辑：优先使用 `date` 字段

**工作量**：中等（需要数据迁移）

### 方案 B：保持现状（当前）

**理由**：
- 数据量不大，性能影响可接受
- 代码逻辑正确，功能可用
- 迁移成本高于收益

## 临时优化建议

如果未来数据量增长导致性能问题，可以考虑：

1. **添加复合索引**：
   ```sql
   CREATE INDEX idx_mood_created_at ON mood_entries(created_at);
   ```

2. **应用层缓存**：
   - 缓存最近 30 天的查询结果
   - 定期刷新缓存

3. **异步预计算**：
   - 定时任务按日期预聚合统计数据
   - 查询时直接读取预聚合结果

## 相关文档

- 时区处理规则：`docs/coding-rules/time-handling-rules.md`
- 标准 bug 模板：`docs/history-bugs/2026-07-13-timeline-custom-block-date-query-datetime-field.md`
- UTC 迁移指南：`docs/guides/utc-migration-guide.md`

## 决策记录

### Mood Entries（✅ 已修复）

- **决策时间**: 2026-07-13
- **决策内容**: 已修复 — 新增 `event_time` 字段，替代 `created_at` 用于查询/排序
- **修复**: m011 迁移 `ALTER TABLE mood_entries ADD COLUMN event_time TEXT` + 回填 `event_time = created_at`
- **数据流**: 前端 `event_time` → `new Date()` 本地时间显示；LLM Agent 本地 `YYYY-MM-DD HH:MM:SS` → execute 层 `local_to_utc_iso()` → UTC ISO 存储
- **决策依据**: `docs/adr/2026-07-13-custom-records-time-string-not-convert.md`（同样设计原则）

### 自定义表 UTC 迁移遗漏（✅ 已修复）

- **决策时间**: 2026-07-13
- **决策内容**: 已修复 — m009 末尾新增动态表迁移逻辑
- **修复**: `_migrate_custom_data_tables()` 遍历 `custom_record_types.slug` 迁移 `custom_<slug>` 的 `created_at`/`updated_at`

### Custom Records 日期查询（✅ 已修复）

- **决策时间**: 2026-07-13
- **决策内容**: 已修复 — 新增 `event_time` 字段，前端组件内 UTC 转换
- **数据流**: 前端 `input[type="date"]` → `toISOStringUTC()` → 后端 `start_time`/`end_time`（UTC ISO） → `WHERE event_time >= ?`
- **决策依据**: `docs/adr/2026-07-13-custom-records-time-string-not-convert.md`

## 未来重构建议

如果满足以下条件之一，建议重构：
1. Mood Entries 单表数据量超过 10 万条
2. 按日期查询响应时间超过 1 秒
3. 用户报告查询缓慢
4. 需要按日期聚合生成报表

重构时参考 `todo_list` 和 `diary` 的表结构设计。
