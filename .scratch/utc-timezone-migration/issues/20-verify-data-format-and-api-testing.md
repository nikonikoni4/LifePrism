# Issue #20: 验证数据时间格式 + 迁移脚本正确性 + FastAPI API 创建测试

## Parent

`.scratch/utc-timezone-migration/prd.md`

## 背景

Issue #16 的 m009 迁移脚本已修改为输出 ISO 8601 格式（`YYYY-MM-DDTHH:MM:SS+00:00`，含时区标识），
而非原来的 `YYYY-MM-DD HH:MM:SS`（无时区标识）。用户已还原数据库（恢复到迁移前状态），
需要在本 issue 中验证：

1. m009 迁移脚本本身格式正确（单元测试已通过，32 个测试全绿）
2. 启动后端后，m009 能正确迁移所有后端数据
3. 通过 FastAPI 文档进行 API 创建调用，新增数据的时间格式正常

**前置条件（已完成）**：
- density_utils.py 的 `TypeError: can't compare offset-naive and offset-aware datetimes` bug 已修复
  - 原因：`sync_service.py` 将 ISO 字符串中的 "T" 替换为空格，导致 `_to_dt` 解析出 naive datetime
  - 修复：`density_utils._to_dt` 在输入为 naive datetime 时补充 UTC tzinfo
- m009 迁移脚本已改为 `strftime('%Y-%m-%dT%H:%M:%S', datetime(field, ?)) || '+00:00'` 输出 ISO 8601 格式
- test_utils.py 的 3 个一致性测试已修复（新增 `_normalize_tz` 辅助函数处理 aware/naive 比较）

## What to build

### 任务 1：确认数据的时间格式和时区是否符合需求

**目标**：验证 m009 迁移后，数据库中所有时间字段都符合 PRD 要求的 ISO 8601 + UTC 格式。

**PRD 要求**（`.scratch/utc-timezone-migration/prd.md`）：
- 数据层（数据库、API）：永远使用 UTC + ISO 8601
- `.isoformat()` 返回 `YYYY-MM-DDTHH:MM:SS.ffffff+00:00` 格式，包含时区标识

**验证步骤**：
1. 对迁移后的数据库 `D:\desktop\软件开发\LifeWatch-AI\localData\dataset\lifewatch_ai.db` 执行 SQL 查询
2. 检查以下表的时间字段格式是否为 `YYYY-MM-DDTHH:MM:SS+00:00`（含 T 分隔符和 +00:00 时区标识）：
   - `habits.created_at`, `habits.updated_at`
   - `goal.created_at`, `goal.updated_at`
   - `diary.created_at`, `diary.updated_at`
   - `todo_list.updated_at`（注意：`todo_list.created_at` 是 UTC 旧表字段，不迁移）
   - `behavior_analysis.start_time`, `behavior_analysis.end_time`
   - `user_app_behavior_log.start_time`, `user_app_behavior_log.end_time`
   - 其他 `_MIGRATION_FIELDS` 中列出的字段
3. 验证排除字段未被迁移（仍为原格式）：
   - `todo_list.created_at`（CURRENT_TIMESTAMP = UTC，不迁移）
   - `timeline_custom_block.created_at`, `timeline_custom_block.updated_at`（UTC 旧表）
4. 验证日期字段（YYYY-MM-DD 格式）未被修改：
   - `diary.date`, `goal.start_date`, `habit_checkins.date` 等
5. 验证所有迁移后的时间值都带 `+00:00` 时区标识

**对比基准**：使用备份数据库 `D:\desktop\软件开发\LifeWatch-AI\localData\dataset\lifewatch_ai - utc-refactor.db`（迁移前）对比验证时间减 8 小时是否正确。

### 任务 2：查看启动后的迁移脚本是否能够正确的迁移当前后端的所有数据

**目标**：启动后端，让 migration_runner 自动执行 m009，验证迁移结果正确。

**验证步骤**：
1. 确认数据库当前状态：`schema_version` 表中 version 应 < 9（未迁移）
2. 启动后端：
   ```
   python -m uvicorn lifeprism.server.main:app --host 127.0.0.1 --port 8000 --reload
   ```
3. 观察启动日志，确认 m009 迁移执行：
   - 应看到 `m009: 开始历史数据时区迁移（UTC+8 → UTC，减 8 小时），共 N 个字段`
   - 应看到每个字段的 `m009: 迁移 xxx.yyy，影响 N 行`
   - 应看到 `m009: 历史数据迁移完成 — 迁移 N 个字段，跳过 N 个，共更新 N 行`
4. 确认 `schema_version` 表新增 version=9 记录
5. 验证迁移覆盖所有 `_MIGRATION_FIELDS` 中列出的字段（共约 80 个字段）
6. 验证含约束的表（`raw_behavior_analysis`, `behavior_analysis`, `user_app_behavior_log`）使用表重建模式正确迁移
7. 抽样验证 20-30 条记录：时间值 = 原值 - 8 小时，格式为 ISO 8601 + `+00:00`

**验证方法**：编写 SQL 查询或 Python 脚本，对比迁移前后数据库。

### 任务 3：通过 FastAPI 文档进行所有 API 创建调用，检查新增数据是否正常

**目标**：使用 FastAPI 自动生成的 API 文档（`/docs`），对所有支持创建的 API 发起调用，验证新增数据的时间字段格式正确。

**验证步骤**：
1. 后端启动后，访问 `http://127.0.0.1:8000/docs` 查看 FastAPI Swagger UI
2. 识别所有支持创建（POST）的 API，至少包括：
   - `POST /api/categories` - 创建分类
   - `POST /api/sub-categories` - 创建子分类
   - `POST /api/todos` - 创建待办
   - `POST /api/goals` - 创建目标
   - `POST /api/diaries` - 创建日记
   - `POST /api/habits` - 创建习惯
   - `POST /api/habit-checkins` - 习惯打卡
   - `POST /api/mood-entries` - 心情记录
   - `POST /api/custom-record-types` - 自定义记录类型
   - `POST /api/custom-records/{slug}` - 自定义记录
   - `POST /api/timeline/blocks` - 时间线自定义块
   - `POST /api/goal-journals` - 目标日志
   - 其他 POST API（根据 /docs 实际列出）
3. 通过 Swagger UI 或 curl 对每个 API 发起创建调用（使用合理的测试数据）
4. 创建后查询数据库，验证新增记录的时间字段：
   - `created_at` 应为 ISO 8601 格式（`YYYY-MM-DDTHH:MM:SS.ffffff+00:00` 或 `YYYY-MM-DDTHH:MM:SS+00:00`）
   - 应包含时区标识（`+00:00`）
   - 时间值应接近当前 UTC 时间（`datetime.now(timezone.utc)`）
5. 验证 API 响应中的时间字段也是 ISO 8601 + UTC 格式
6. 对于含 `start_time`/`end_time` 的 API（如 timeline blocks），验证时间字段格式正确

**验证方法**：
- 通过 Swagger UI 手动调用，或编写 Python 脚本使用 `requests` 库批量调用
- 每次创建后，用 SQL 查询数据库验证新增记录的时间格式

## Acceptance criteria

### 任务 1
- [ ] 已查询迁移后数据库，所有 `_MIGRATION_FIELDS` 中的字段都为 `YYYY-MM-DDTHH:MM:SS+00:00` 格式
- [ ] 已验证排除字段（UTC 旧表）未被修改
- [ ] 已验证日期字段（YYYY-MM-DD）未被修改
- [ ] 已验证所有迁移后的时间值都带 `+00:00` 时区标识
- [ ] 已对比备份数据库验证时间减 8 小时正确

### 任务 2
- [ ] 后端启动时 m009 迁移自动执行
- [ ] 迁移日志完整（所有字段都有迁移记录）
- [ ] `schema_version` 表新增 version=9 记录
- [ ] 含约束的表使用表重建模式正确迁移
- [ ] 抽样验证 20-30 条记录时间值正确

### 任务 3
- [ ] 已通过 FastAPI /docs 识别所有 POST 创建 API
- [ ] 已对每个创建 API 发起调用并成功创建数据
- [ ] 已验证新增记录的 `created_at` 为 ISO 8601 + UTC 格式
- [ ] 已验证新增记录的时间值接近当前 UTC 时间
- [ ] 已验证 API 响应中的时间字段格式正确
- [ ] 已验证含 `start_time`/`end_time` 的 API 时间字段格式正确

## Blocked by

- Issue #16 - 数据库历史数据迁移脚本（m009 已修改为 ISO 8601 格式输出）
- density_utils.py bug 修复（已完成）
- test_utils.py 一致性测试修复（已完成）

## 注意事项

1. **数据库还原**：用户已还原数据库到迁移前状态，m009 将在启动时首次执行
2. **不要修改 m009 脚本**：m009 已修改完成并通过 32 个单元测试，本 issue 只验证不修改
3. **不要修改 density_utils.py**：bug 已修复并通过 12 个测试，本 issue 只验证不修改
4. **如发现问题**：记录问题详情，但不要自行修复，报告给主 agent 由用户决策
5. **数据库路径**：
   - 迁移后数据库：`D:\desktop\软件开发\LifeWatch-AI\localData\dataset\lifewatch_ai.db`
   - 备份数据库（迁移前）：`D:\desktop\软件开发\LifeWatch-AI\localData\dataset\lifewatch_ai - utc-refactor.db`
