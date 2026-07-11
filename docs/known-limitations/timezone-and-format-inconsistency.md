---
created_at: 2026-07-12
updated_at: 2026-07-12
category: data-sync
severity: high
status: acknowledged
---

# 已知限制：时区和时间格式不一致

## 概述

当前系统在时区处理和时间格式上存在多处不一致，可能导致数据同步失败、时间显示错误和业务逻辑异常。本文档记录这些已知限制及其影响范围。

## 问题 1：时区不一致

### 问题描述

系统中存在三种不同的时区使用方式，导致时间戳无法正确比较：

| 时区类型 | 使用位置 | 数量 | 格式示例 |
|---------|---------|------|---------|
| **本地时间（naive）** | 大部分数据库字段 | 80+ | `2026-07-12 00:29:54` |
| **UTC 时间** | 3个旧迁移遗留字段 | 3 | `2026-07-11 16:29:54` |
| **UTC 时间** | 同步模块、部分 Provider | ~10 | `2026-07-11T16:29:54Z` |

### 具体问题

#### 1.1 旧迁移遗留（P0 - 严重）

以下 3 个字段使用 `CURRENT_TIMESTAMP`（UTC），而其他 45 张表使用 `datetime('now', 'localtime')`（本地时间）：

- `todo_list.created_at`
- `timeline_custom_block.created_at`
- `timeline_custom_block.updated_at`

**影响**：
- UTC+8 时区下，这 3 个字段比其他字段早 8 小时
- 数据同步时 LWW 比较失效（`2026-07-11 16:29:54` vs `2026-07-12 00:29:54` 字符串比较错误）
- 前端展示时间混乱（同一列表中部分记录时间偏移 8 小时）

#### 1.2 前后端时区不一致（P0 - 严重）

**后端**：
- 大部分代码使用 `datetime.now()`（本地时间，naive datetime）
- 同步模块使用 `datetime.now(timezone.utc)`（UTC）

**前端**：
- 违规代码使用 `new Date().toISOString()`（UTC）
- 正确代码使用 `toLocalDateTimeString()`（本地时间）

**影响**：
- 前端写入的 `updated_at` 为 UTC 时间（如 `2026-07-11T16:30:00Z`）
- 后端写入的 `updated_at` 为本地时间（如 `2026-07-12 00:30:00`）
- LWW 冲突解决失败（字符串比较 `"2026-07-11T16:30:00Z" > "2026-07-12 00:30:00"` 结果错误）

#### 1.3 无全局时区配置

**当前状态**：
- 后端无 `timezone` 配置项，依赖系统默认时区
- 前端无时区配置，依赖浏览器时区
- Electron 未设置 `process.env.TZ`

**风险**：
- 如果云端服务器部署在海外（如 UTC 时区），本地和云端时间戳将完全错位
- 用户在不同时区使用应用时，数据同步可能失败
- 无法统一控制时区行为

### 影响范围

**数据同步**：
- 30+ 张同步表的 LWW 冲突解决可能失效
- 增量同步查询 `updated_at > last_sync_time` 可能遗漏或重复数据
- 文件同步的 mtime 比较（已修复，使用 UTC）

**业务逻辑**：
- 按时间排序时，UTC 字段和本地时间字段混合排序错误
- 时间范围查询可能遗漏数据
- 习惯打卡、目标日志等时间敏感功能可能异常

**用户体验**：
- 部分时间显示比实际早/晚 8 小时
- 日历、报告等组件中时间不一致

## 问题 2：时间格式不一致

### 问题描述

数据库中存在两种时间格式混用，容易混淆且可能导致解析错误：

| 格式类型 | 示例 | 生成方法 | 使用比例 |
|---------|------|---------|---------|
| **标准格式**（正确） | `2026-07-12 00:29:54` | `.strftime("%Y-%m-%d %H:%M:%S")` | 68% |
| **ISO 格式**（不一致） | `2026-07-12T00:29:54.123456` | `.isoformat()` | 3% |
| **日期格式** | `2026-07-12` | `.strftime("%Y-%m-%d")` | 12% |
| **NULL/无数据** | - | - | 17% |

### 具体问题

#### 2.1 同一表内格式不一致（P1 - 高优先级）

**最严重案例 - `habit_challenges` 表**：
```
created_at: 2026-05-15 00:19:32       （标准格式 ✅）
updated_at: 2026-05-15T00:19:32.413120 （ISO 格式 ❌）
```

**原因**：
- `created_at` 由 SQLite DEFAULT 自动生成（`datetime('now', 'localtime')`）
- `updated_at` 由代码写入（`datetime.now().isoformat()`）

**影响**：
- 字符串比较 `"2026-05-15 00:19:32" > "2026-05-15T00:19:32.413120"` 结果不可预测
- 前端解析需要兼容两种格式
- 数据一致性验证困难

#### 2.2 代码写入格式不一致（P1 - 高优先级）

**问题位置**：
- `lw_base_data_provider.py:1184`: `datetime.now().isoformat()` - 影响 35 张表
- `habit_providers.py:403`: `datetime.now().isoformat()`（带T）
- `habit_providers.py:404`: `datetime.now().strftime("%Y-%m-%d %H:%M:%S")`（不带T）
- `map_cache_providers.py:311, 672`: `datetime.now().isoformat()`

**验证结果**（实际数据库查询）：
- `chat_session.created_at`: `2026-02-25T10:25:16.030220` ❌
- `chat_session.updated_at`: `2026-02-25T10:25:16.054716` ❌
- `habits.updated_at`: 部分记录为 ISO 格式 ❌
- 其他大部分表：标准格式 ✅

#### 2.3 SQLite DEFAULT 与 Python 代码格式不一致

| 来源 | 格式 | 示例 | 生成方法 |
|------|------|------|---------|
| SQLite DEFAULT | `YYYY-MM-DD HH:MM:SS` | `2026-07-12 00:29:54` | `datetime('now', 'localtime')` |
| Python `.isoformat()` | `YYYY-MM-DDTHH:MM:SS.ffffff` | `2026-07-12T00:29:54.123456` | `datetime.now().isoformat()` |
| Python `.strftime()` | `YYYY-MM-DD HH:MM:SS` | `2026-07-12 00:29:54` | `datetime.now().strftime(...)` |

**影响**：
- 新插入记录（SQLite DEFAULT）与更新记录（Python 代码）格式不一致
- 同一表中新旧数据格式混合
- 数据迁移和备份时容易出错

### 影响范围

**数据一致性**：
- 同一表内不同记录格式不一致
- 字符串排序和比较结果不可预测

**开发维护**：
- 代码中不清楚应该用哪种格式
- 前端需要兼容多种格式的解析逻辑
- 新增字段时容易引入新的格式不一致

**性能**：
- 字符串比较可能比时间戳比较慢
- 索引优化受影响

## 问题 3：前端时间字段违规

### 问题描述

前端有 27 处生产代码违反 `dateUtils.ts` 规则，直接使用 `.toISOString()` 导致：
1. 生成 UTC 时间而非本地时间
2. 在 UTC+ 时区的午夜前后，日期字段会错位一天

详见：`docs/generated/frontend-time-usage-report.md`

**典型 bug 场景**：
- 用户在 UTC+8 时区的 2026-07-12 00:30 完成任务
- 代码使用 `new Date().toISOString().split('T')[0]` → `"2026-07-11"`
- 实际应该记录 `"2026-07-12"`

### 影响范围

**P0 级别**（5 处）：
- 计划书 `updatedAt` 字段（4 处）
- 扩展目录 `created_at` 字段（1 处）

**P1 级别**（7 处）：
- Todo 完成日期、里程碑完成日期、目标默认日期等

## 当前假设（脆弱的前提）

系统能够正常运行，依赖于以下**未明确保证**的假设：

1. **本地和云端服务器在同一时区**
   - 如果云端部署在海外（UTC），所有时间戳将错位 8 小时

2. **所有时间戳都能正确字符串比较**
   - 实际上混合格式会导致比较失败

3. **前端能正确解析两种格式**
   - 需要手动兼容 `YYYY-MM-DD HH:MM:SS` 和 `YYYY-MM-DDTHH:MM:SS`

4. **用户不会跨时区使用**
   - 如果用户旅行或更换设备，数据可能出现时间偏移

## 业界最佳实践对比

根据业界共识（Laravel、Spring Boot、FastAPI 等框架官方建议）：

✅ **应该做的**：
- 数据库统一存储 UTC 时间
- 使用 timezone-aware datetime（如 `datetime.now(timezone.utc)`）
- 仅在展示层转换为用户本地时区
- 不依赖数据库的时区转换函数

❌ **当前的问题**：
- 使用 naive datetime（无时区信息）
- 混合使用本地时间和 UTC
- 格式不统一
- 无全局时区配置

## 相关文档

- **调查报告**：
  - `docs/generated/backend-time-fields-inventory.md` - 完整时间字段清单
  - `docs/generated/backend-timezone-issues.md` - 时区问题详细分析
  - `docs/generated/backend-time-format-verification.md` - 格式验证结果
  - `docs/generated/frontend-time-usage-report.md` - 前端时间使用报告

- **设计决策**：
  - 待补充：为什么选择本地时间而非 UTC（需记录历史原因）

- **修复计划**：
  - 待补充：时区统一改造方案（考虑采用 UTC 最佳实践）

## 注意事项

**在修复前需要注意**：
1. 数据迁移需要时区转换（UTC → 本地时间 或 本地时间 → UTC）
2. 前后端必须同步修复，否则问题更严重
3. 历史数据可能无法准确判断原始时区
4. 需要通知用户可能的数据时间偏移

**临时缓解措施**：
- 确保本地和云端服务器使用相同时区
- 避免跨时区使用
- 谨慎修改时间相关代码
