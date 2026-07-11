# PRD: 时间处理迁移到 UTC 时区和 ISO 8601 格式

## Problem Statement

系统当前使用本地时区存储时间数据，导致严重的数据同步和一致性问题：

1. **数据同步失败**：80+ 张表使用本地时区，3 张旧表使用 UTC，时区不一致导致 LWW（Last-Write-Wins）冲突解决时字符串比较错误，数据同步失败
2. **前端日期错位**：前端 27+ 处违规使用 `.toISOString().split('T')[0]`，在 UTC+ 时区的午夜前后会导致日期减一天
3. **时间格式混乱**：同一表内混合使用标准格式（`YYYY-MM-DD HH:MM:SS`）和 ISO 格式（`YYYY-MM-DDTHH:MM:SS.ffffff`）
4. **未来扩展风险**：如果云端部署到海外服务器，本地和云端时间戳将错位（如 UTC 时区服务器与 UTC+8 本地相差 8 小时）

作为开发者，我需要系统统一使用 UTC 时区和 ISO 8601 格式存储时间，确保数据同步正确、前后端一致、支持未来跨时区部署。

## Solution

采用业界最佳实践：**后端统一使用 UTC 时区，存储和传输使用 ISO 8601 格式；前端接收后自动转为 Date 对象（浏览器自动处理时区转换），显示时使用本地时区**。

**核心原则**：
- 数据层（数据库、API）：永远使用 UTC + ISO 8601
- 逻辑层（后端计算、前端计算）：使用 aware datetime（Python）或 Date 对象（JavaScript）
- 展示层（前端 UI）：自动转为用户本地时区显示

**技术方案**：
- 后端所有 `datetime.now()` 改为 `datetime.now(timezone.utc)`
- 后端所有时间序列化使用 `.isoformat()` 而非 `.strftime()`
- 数据库表 DEFAULT 从 `datetime('now', 'localtime')` 改为 `datetime('now')`（SQLite UTC）
- 前端所有 `toISOString().split('T')[0]` 改为 `toLocalDateString(date)`（已有工具函数）
- 历史数据迁移：假设旧数据为 UTC+8（北京时间），统一减 8 小时转为 UTC

## User Stories

1. 作为数据同步模块的开发者，我希望所有时间戳使用统一时区（UTC），这样 LWW 冲突解决时字符串比较才能正确判断新旧
2. 作为后端开发者，我希望所有时间生成代码使用 `datetime.now(timezone.utc)`，这样代码审查时能一眼看出时区意图
3. 作为前端开发者，我希望后端 API 返回的时间字符串带有明确的时区标识（ISO 8601 格式），这样我能安全地用 `new Date(isoString)` 解析
4. 作为前端开发者，我希望有统一的时间格式化工具函数（`toLocalDateString`、`toLocalDateTimeString`），这样我不需要重复编写格式化逻辑
5. 作为前端开发者，我希望所有日期选择、日历组件使用正确的本地时间方法（`getFullYear()`、`getMonth()`），而不是 `toISOString()`，这样 UTC+ 时区的用户在午夜前后不会看到错误的日期
6. 作为数据库管理员，我希望所有表的 DEFAULT 时间戳使用 `datetime('now')`（SQLite UTC），这样新插入的数据自动使用 UTC 时间
7. 作为数据库管理员，我希望有迁移脚本能安全地将历史数据从本地时区转为 UTC，这样旧数据和新数据时区一致
8. 作为定时任务开发者，我希望明确定时任务的触发时间是基于 UTC 还是本地时区，这样任务不会因为服务器时区变化而触发错误
9. 作为定时任务开发者，我希望任务逻辑中的"昨天"、"今天"等相对时间概念明确基于哪个时区，这样数据查询范围不会出错
10. 作为 API 开发者，我希望前端发送的时间参数也是 ISO 8601 格式，这样后端解析时不会因为格式不一致出错
11. 作为数据同步服务的开发者，我希望 `last_sync_time` 使用 UTC 时间戳，这样本地和云端比较时不会因为时区差导致重复同步或遗漏数据
12. 作为日志查看者，我希望日志中的时间戳标注清楚是 UTC 还是本地时区，这样调试时不会混淆时间线
13. 作为测试工程师，我希望有单元测试覆盖时区转换逻辑，这样代码重构时不会引入时区相关的回归 bug
14. 作为测试工程师，我希望有集成测试模拟跨时区场景（本地 UTC+8，服务器 UTC），这样能验证系统在不同时区下正常工作
15. 作为前端开发者，我希望 API 文档明确标注所有时间字段的格式和时区，这样我不需要猜测或查看后端代码
16. 作为后端开发者，我希望有代码规范明确禁止使用 `datetime.now()`（无时区），这样代码审查时能强制检查
17. 作为代码审查者，我希望有 linter 规则检查前端是否使用了 `.toISOString()`（除了发送给后端的场景），这样能自动发现违规代码
18. 作为数据分析师，我希望导出的数据使用标准的 ISO 8601 格式，这样导入到其他工具（如 Excel、Tableau）时时间能正确识别
19. 作为用户，我希望前端显示的时间自动转为我的本地时区，这样我不需要手动计算时差
20. 作为开发者，我希望数据库查询中的时间范围条件（如 `WHERE date(created_at) = '2026-01-01'`）在 UTC 时区下仍然正确，这样统计报表不会因为时区变化出错
21. 作为开发者，我希望迁移方案分阶段执行（先修改代码，再迁移数据），这样出问题时能及时回滚
22. 作为开发者，我希望有详细的迁移前后对比清单，这样能确认每个模块都已正确迁移
23. 作为开发者，我希望有回退方案（保留历史数据备份），这样迁移失败时能快速恢复
24. 作为项目经理，我希望有迁移影响范围评估（影响哪些模块、哪些 API、哪些前端组件），这样能合理安排资源和时间

## Implementation Decisions

### 1. 后端代码修改

**时间生成统一使用 UTC**：
- 所有 `datetime.now()` 改为 `datetime.now(timezone.utc)`
- 影响范围：58 个文件（通过 grep 排查到）
- 修改模式：机械替换，但需人工审查每处修改的上下文（确保没有其他依赖本地时区的逻辑）

**时间序列化统一使用 ISO 8601**：
- 所有 `.strftime('%Y-%m-%d %H:%M:%S')` 改为 `.isoformat()`
- 所有 `.strftime('%Y-%m-%d')` 改为 `.date().isoformat()`（仅日期部分）
- 影响范围：58 个文件（通过 grep 排查到）
- 注意：`.isoformat()` 返回 `YYYY-MM-DDTHH:MM:SS.ffffff+00:00` 格式，包含时区标识

**时间解析统一处理时区**：
- 所有 `datetime.fromisoformat(string)` 需要确认返回的是 aware datetime
- 如果接收到无时区信息的字符串，使用 `.replace(tzinfo=timezone.utc)` 补充时区
- 影响范围：所有接收外部时间输入的地方（API 参数、文件读取、数据库查询）

**数据库 DEFAULT 改为 UTC**：
- 所有表定义中的 `datetime('now', 'localtime')` 改为 `datetime('now')`（SQLite 的 `datetime('now')` 返回 UTC）
- 影响范围：所有 `CREATE TABLE` 语句和迁移脚本
- 注意：已有表需要用 `ALTER TABLE` 修改 DEFAULT

**定时任务时区语义明确**：
- `schedule_service.py` 中的 Cron 表达式 `"0 10 * * *"` 需要明确是 UTC 10:00 还是本地 10:00
- APScheduler 默认使用本地时区，需要显式设置 `timezone='UTC'`
- `_dreaming()` 函数中的"昨天"计算（`datetime.now() - timedelta(days=1)`）改为 `datetime.now(timezone.utc) - timedelta(days=1)`
- `_should_execute_cron_today()` 中的"今天"判断（`datetime.now().strftime("%Y-%m-%d")`）改为 `datetime.now(timezone.utc).strftime("%Y-%m-%d")`
- 影响范围：`schedule_service.py`、所有定时任务函数

### 2. 前端代码修改

**违规代码修复**：
- 所有 `toISOString().split('T')[0]` 改为 `toLocalDateString(date)`（已有工具函数）
- 影响范围：22+ 处（已通过 grep 排查到具体文件）
- 文件清单：
  - `frontend/apps/goals/hooks/useGoalStore.ts:204`
  - `frontend/apps/lifewatch/pages/reports/components/DailyReviewTab.tsx:38, 119, 168, 187`
  - `frontend/apps/lifewatch/pages/reports/components/WeeklyReviewTab.tsx:36-37, 118, 122`
  - `frontend/apps/goals/components/views/CalendarView/components/DateGrid.tsx:21, 66, 89`
  - `frontend/apps/goals/components/views/GoalListView/components/AddGoalModal.tsx:21`
  - `frontend/apps/goals/components/views/GoalListView/components/JournalEntryModal.tsx:22`
  - `frontend/apps/lifewatch/pages/usage/UsagePage.tsx:28`
  - `frontend/my-ui-kit/ui-kit/todoItem/TodoItem.tsx:199`
  - `frontend/my-ui-kit/ui-kit/todoItem/TodoItemDetailed.tsx:195`
  - `frontend/core/services/reportCacheService.ts:290`
  - `frontend/apps/lifewatch/pages/reports/mockData.ts:66`

**时间工具函数扩展**：
- `frontend/core/utils/dateUtils.ts` 中的 `toLocalDateString()` 和 `toLocalDateTimeString()` 已正确实现
- 新增 `parseISOString(isoString: string): Date` 工具函数，统一处理后端返回的 ISO 字符串
- 新增 `toISOStringUTC(date: Date): string` 工具函数，用于前端发送时间给后端

**API 响应处理**（可选，作为后续优化）：
- 考虑在 API 调用层添加响应拦截器，自动将时间字符串转为 Date 对象
- 优先级：低（当前方案已能解决问题，这是进一步优化）

### 3. 数据库历史数据迁移

**迁移策略**：
- 假设所有历史数据都是 UTC+8（北京时间），统一减 8 小时转为 UTC
- 3 张旧表（已经是 UTC）不需要迁移，需要在迁移脚本中排除

**迁移脚本设计**：
- 创建新的迁移脚本 `lifeprism/repository/migrations/scripts/m008_migrate_to_utc.py`
- 步骤：
  1. 读取 `docs/generated/backend-time-fields-inventory.md` 获取所有时间字段清单
  2. 排除 3 张已经是 UTC 的旧表
  3. 对每个表的每个时间字段执行 `UPDATE` 语句：
     ```sql
     UPDATE table_name
     SET time_field = datetime(time_field, '-8 hours')
     WHERE time_field IS NOT NULL;
     ```
  4. 记录迁移日志（表名、字段名、影响行数）
  5. 验证迁移结果（抽样检查几条数据）

**迁移执行流程**：
1. 在测试环境执行迁移脚本，验证结果
2. 备份生产数据库
3. 在生产环境执行迁移脚本
4. 验证关键功能（数据同步、定时任务、前端时间显示）
5. 监控错误日志

**回退方案**：
- 保留迁移前的数据库备份
- 如果发现严重问题，恢复备份
- 如果只是部分数据错误，可以反向迁移（加 8 小时）

### 4. 隐性依赖排查和修复

**定时任务触发时间**：
- 问题：Cron 表达式 `"0 10 * * *"` 在本地时区是"每天 10:00"，迁移到 UTC 后变为"每天 UTC 10:00"（北京时间 18:00）
- 决策：保持用户预期的"本地时间 10:00"触发，需要将 Cron 表达式改为 `"0 2 * * *"`（UTC 02:00 = 北京时间 10:00）
- 影响范围：`schedule_service.py` 中的 `_SYSTEM_CRON_JOB_TIME`

**时间范围查询**：
- 问题：数据库查询中的 `date(created_at) = '2026-01-01'` 在 UTC 时区下可能跨两个本地日期
- 示例：本地 2026-01-01 00:00 ~ 23:59 对应 UTC 2025-12-31 16:00 ~ 2026-01-01 15:59
- 决策：查询时需要显式转换时区，或者查询条件改为时间戳范围
- 影响范围：所有按日期过滤的查询（需要逐个审查）

**日志和调试**：
- 问题：日志中的时间戳从本地时区（可读性好）变为 UTC（可读性差）
- 决策：日志时间戳保持 UTC（与数据一致），但在日志消息中可以注明"UTC"
- 影响范围：`lifeprism/utils/logger.py` 日志格式配置

**前端日期选择器**：
- 问题：用户选择"今天"时，前端需要传递本地时间的午夜（00:00），而非 UTC 午夜
- 决策：前端选择日期后，使用 `toLocalDateTimeString()` 转为 `YYYY-MM-DDTHH:MM:SS` 格式，后端收到后再 `.replace(tzinfo=timezone.utc)` 强制解释为 UTC
- 影响范围：所有日期选择器、日历组件

**统计报表中的时间分组**：
- 问题：按天分组统计（如"每日活跃用户"）需要基于用户本地时区的"天"
- 决策：在查询时使用 SQLite 的 `datetime(created_at, '+8 hours')` 将 UTC 时间转回本地时区再分组
- 影响范围：所有统计查询（`report_service.py`、`activity_stats_builder.py`）

### 5. 测试策略

**单元测试**：
- 测试时间生成函数（确保返回 UTC 时间）
- 测试时间序列化函数（确保返回 ISO 8601 格式）
- 测试时间解析函数（确保正确处理带时区和不带时区的字符串）
- 测试前端工具函数（`toLocalDateString`、`toLocalDateTimeString`）

**集成测试**：
- 模拟跨时区场景：本地 UTC+8，服务器设置为 UTC，验证数据同步正确
- 模拟前端午夜场景：本地时间 23:59 和 00:01，验证日期选择正确
- 模拟定时任务触发：验证任务在预期的本地时间触发

**回归测试**：
- 运行所有现有测试套件，确保没有引入新 bug
- 特别关注时间相关的测试用例

**手动测试清单**：
- 数据同步：本地修改数据 → 同步到云端 → 云端修改数据 → 同步回本地，验证时间戳正确
- 前端时间显示：查看目标创建时间、日记日期、习惯打卡时间，验证显示正确
- 定时任务：等待定时任务触发，验证触发时间正确
- 日历组件：在不同日期点击，验证日期选择正确
- 统计报表：查看每日/每周/每月统计，验证时间分组正确

### 6. 文档更新

**API 文档**：
- 在 `docs/api/` 中明确标注所有时间字段的格式和时区
- 示例：`created_at: string (ISO 8601 format, UTC timezone, e.g., "2026-07-11T02:30:45.123456+00:00")`

**开发规范**：
- 在 `docs/coding-rules/backend-error-handling.md` 中新增"时间处理规范"章节
- 明确禁止使用 `datetime.now()`（无时区），必须使用 `datetime.now(timezone.utc)`
- 明确禁止前端使用 `.toISOString().split('T')[0]`，必须使用 `toLocalDateString()`

**已知限制文档**：
- 迁移完成后，删除 `docs/known-limitations/timezone-and-format-inconsistency.md`

## Testing Decisions

### 测试原则

**只测试外部行为，不测试实现细节**：
- 测试时间生成函数返回的时间是否带时区信息（`tzinfo` 不为 None），而不是测试是否调用了 `datetime.now(timezone.utc)`
- 测试时间序列化结果是否符合 ISO 8601 格式（正则匹配），而不是测试是否调用了 `.isoformat()`
- 测试前端显示的日期是否正确，而不是测试是否调用了 `toLocalDateString()`

### 测试模块

**后端单元测试**：
- 新增 `test/core/unit/utils/test_datetime_utils.py`：测试时间生成、序列化、解析函数
- 修改现有的 provider 测试：验证返回的时间字段是 ISO 8601 格式

**前端单元测试**：
- 扩展 `frontend/core/utils/dateUtils.test.ts`：补充 UTC 时区场景的测试用例
- 新增测试用例：验证 `toLocalDateString()` 在 UTC 午夜前后返回正确日期

**集成测试**：
- 新增 `test/core/integration/test_timezone_sync.py`：模拟跨时区数据同步场景
- 新增 `test/core/integration/test_schedule_utc.py`：验证定时任务在 UTC 时区下触发时间正确

### 参考已有测试

**后端测试参考**：
- `test/core/unit/server/test_schedule_service.py` - 定时任务测试模式
- `test/core/unit/llm/test_llm_dataset_provider.py` - 时间字段测试模式

**前端测试参考**：
- `frontend/core/utils/dateUtils.test.ts` - 时间工具函数测试模式

## Out of Scope

以下内容不在本次 PRD 范围内，作为后续优化方向：

1. **前端 API 响应拦截器**：统一将时间字符串转为 Date 对象（优先级：低）
2. **扩大 date-fns 使用范围**：替换所有手写的时间格式化逻辑（优先级：低）
3. **Linter 规则**：自动检查前端是否使用了 `.toISOString()`（优先级：中）
4. **数据库查询优化**：将所有 `date(created_at)` 改为时间戳范围查询（优先级：中，作为性能优化）
5. **用户时区配置**：允许用户手动选择显示时区（当前假设用户时区与系统时区一致，优先级：低）
6. **历史数据时区标注**：对于迁移前后交界期的数据，标注是否已迁移（优先级：低）

## Further Notes

### 迁移风险

**高风险点**：
1. 数据库历史数据迁移可能出错（时区假设错误、迁移脚本 bug）
2. 定时任务触发时间可能错位（Cron 表达式未正确调整）
3. 前端午夜场景可能仍有遗漏的 `.toISOString()` 使用

**缓解措施**：
1. 在测试环境充分验证迁移脚本
2. 迁移前备份生产数据
3. 迁移后持续监控错误日志
4. 第一个版本可以支持双格式读取（兼容模式），验证通过后再移除

### 迁移成本估算

**代码修改**：
- 后端：约 100+ 处修改（58 个文件 × 平均 2 处/文件）
- 前端：约 30 处修改（22 处违规 + 工具函数扩展）
- 数据库：所有表 DEFAULT 修改 + 迁移脚本编写

**测试验证**：
- 单元测试编写：约 20 个测试用例
- 集成测试编写：约 10 个测试场景
- 手动测试：约 2 人日

**文档更新**：
- API 文档、开发规范、已知限制：约 0.5 人日

**总计**：约 5-7 人日

### 业界参考

- **Laravel**：强制使用 UTC 存储，在 Eloquent ORM 中自动处理时区转换
- **ActivityWatch**：桌面应用，但仍使用 UTC 存储，证明即使是本地应用也需要 UTC
- **FastAPI**：官方文档推荐使用 `datetime.now(timezone.utc)` 和 ISO 8601 格式
- **Django**：`USE_TZ = True` 强制使用时区感知的 datetime
