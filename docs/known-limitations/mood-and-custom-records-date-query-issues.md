# Mood Entries 和 Custom Records 日期查询问题

## 元信息

- **发现时间**: 2026-07-13
- **状态**: ❌ 未修复（已知限制）
- **影响范围**: Mood Entries API、Custom Records API
- **问题类型**: 数据表设计问题 - 缺少独立日期字段
- **严重程度**: 中（功能可用，但查询效率低）

## 问题描述

### 1. Mood Entries API

**表结构**：
```sql
CREATE TABLE mood_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mood_level INTEGER,
    note TEXT,
    created_at TEXT,  -- UTC ISO 8601
    updated_at TEXT
);
```

**API 查询参数**：
```typescript
// frontend/apps/mindspace/components/mood/moodApi.ts
GET /api/v2/mood/entries?start_date=2026-07-01&end_date=2026-07-31
```

**问题**：
- 表中只有 `created_at` datetime 字段（UTC）
- **没有独立的 `date` 字段**用于快速按日期查询
- 每次查询都需要在后端将日期范围转换为 UTC 时间范围
- 无法在数据库层建立基于日期的索引

### 2. Custom Records API

**表结构**：
```sql
CREATE TABLE custom_records_<type_id> (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    field_1 TEXT,
    field_2 TEXT,
    created_at TEXT,  -- UTC ISO 8601
    updated_at TEXT
);
```

**API 查询参数**：
```typescript
// frontend/apps/custom-records/api.ts
GET /api/v2/custom-records/:typeId/entries?start_date=2026-07-01&end_date=2026-07-31
```

**问题**：
- 表中只有 `created_at/updated_at` datetime 字段
- **没有独立的 `date` 字段**
- 按日期聚合统计时需要额外的时间转换

## 当前实现

### 后端处理逻辑

两个 API 都在后端 Service 层将日期转换为 UTC 时间范围：

```python
# mood_service.py / custom_records_service.py
from lifeprism.utils.time_utils import build_utc_time_range

def get_entries(start_date: str, end_date: str):
    start_time, end_time = build_utc_time_range(start_date, end_date)
    # start_time: "2026-06-30T16:00:00.000Z" (UTC+8 → UTC)
    # end_time: "2026-07-31T15:59:59.999Z"
    
    results = repository.query_by_time_range(start_time, end_time)
    return results
```

### 查询流程

1. 前端：传本地日期范围 `start_date=2026-07-01&end_date=2026-07-31`
2. Service 层：调用 `build_utc_time_range()` 转换为 UTC 时间范围
3. Repository 层：`WHERE created_at >= ? AND created_at <= ?`
4. 数据库：扫描 `created_at` datetime 字段

## 为什么是"已知限制"而非"bug"

### 与 Timeline Custom Block 的区别

| 对比项 | Timeline Custom Block（bug） | Mood/Custom Records（限制） |
|--------|------------------------------|----------------------------|
| 表结构 | 只有 `start_time/end_time` datetime | 只有 `created_at/updated_at` datetime |
| API 参数 | 传日期 `date=2026-07-13` | 传日期范围 `start_date/end_date` |
| 后端处理 | ❌ 直接拼接字符串（错误） | ✅ 使用 `build_utc_time_range()` 转换 |
| 查询结果 | ❌ 字符串比较失败，查不到数据 | ✅ 查询正确，但效率低 |
| 问题性质 | 代码 bug（逻辑错误） | 表设计限制（缺少日期字段） |

**Custom Block 是 bug**：代码逻辑错误导致查询失败。

**Mood/Custom Records 是限制**：
- 代码逻辑正确（后端转换了时间范围）
- 查询结果准确
- 但因为缺少独立 `date` 字段，无法优化查询性能

## 影响

### 性能影响

1. **无法建立日期索引**：
   - `created_at` 是完整时间戳，无法基于日期快速过滤
   - 需要扫描时间范围内的所有记录

2. **时区转换开销**：
   - 每次查询都需要调用 `build_utc_time_range()`
   - 需要读取 `user_timezone` 配置

3. **聚合统计效率低**：
   - 按日期分组统计时，需要在应用层转换时间
   - 无法利用数据库的 `DATE()` 函数

### 功能影响

- ✅ 查询功能正常（结果正确）
- ✅ 时区处理正确
- ⚠️ 大数据量时查询较慢
- ⚠️ 按日期聚合时需要额外转换

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

- **决策时间**: 2026-07-13
- **决策者**: 架构评审
- **决策内容**: 暂不修复，作为已知限制记录
- **理由**:
  1. 当前实现功能正确，无数据错误
  2. 性能影响在可接受范围内
  3. 添加 `date` 字段需要数据迁移，成本高
  4. 优先修复 Custom Block 等有数据错误的 bug

## 未来重构建议

如果满足以下条件之一，建议重构：
1. Mood Entries 单表数据量超过 10 万条
2. 按日期查询响应时间超过 1 秒
3. 用户报告查询缓慢
4. 需要按日期聚合生成报表

重构时参考 `todo_list` 和 `diary` 的表结构设计。
