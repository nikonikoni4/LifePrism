# Issue #26: 剩余模块时间显示统一 + goal_journal 修复

## Parent

`.scratch/utc-timezone-migration/prd.md`

## What to build

覆盖其他 slice 未涉及的模块，统一前端时间显示，并修复 `goal_journal` 的 UPDATE 不刷新 `updated_at` 问题。

**架构原则**：
- 后端 API：保持 UTC ISO 8601 透传，不做转换
- 前端组件：就地调用 `utcToLocalDisplay()` 转换为本地时区显示

## Part 1: 剩余模块前端时间显示修复

审查报告中未在其他 slice 覆盖的前端时间显示位置，包括：

1. **habits 模块**
   - 检查习惯列表、打卡记录、热力图等的时间显示
   - 修复直接显示 UTC 时间的位置

2. **goals 模块**
   - 检查目标列表、目标日志、日历视图等的时间显示
   - 修复直接显示 UTC 时间的位置

3. **diary 模块**
   - 检查日记列表、日记详情的时间显示
   - 修复直接显示 UTC 时间的位置

4. **mood 模块**
   - 检查心情记录、心情趋势图的时间显示
   - 修复直接显示 UTC 时间的位置

5. **todos 模块**
   - 检查待办列表的时间显示
   - 修复直接显示 UTC 时间的位置

6. **reports 模块**（显示部分，筛选在 Issue #23）
   - 检查报告页面的时间显示
   - 修复直接显示 UTC 时间的位置

7. **settings 模块**
   - 检查设置界面的时间显示（如有）

8. **lifewatch 主界面**
   - 检查活动日志、行为分析的时间显示
   - 修复直接显示 UTC 时间的位置

**修复方式**：所有时间显示统一调用 `utcToLocalDisplay()` 或 `utcToLocalDate()`

## Part 2: goal_journal PATCH updated_at 修复

**问题**：`goal_journal` 的 PATCH 接口不刷新 `updated_at` 字段。

**需要修复**：
- `lifeprism/server/providers/journal_provider.py` 的 `update_journal` 方法
- 在 SET 子句中追加 `updated_at = ?` 并绑定 `get_utc_now_iso()`

**注意**：这是后端存储层的修复，不是"对外接口转换"。`updated_at` 是系统自动管理的字段，应该在任何 UPDATE 时自动刷新。

## Part 3: plan_doc PATCH updated_at 刷新（如需要）

检查 `plan_doc` 的 PATCH 是否正确刷新 `updated_at`，如不刷新则修复。

## Acceptance criteria

### Part 1
- [ ] habits 模块时间显示修复
- [ ] goals 模块时间显示修复
- [ ] diary 模块时间显示修复
- [ ] mood 模块时间显示修复
- [ ] todos 模块时间显示修复
- [ ] reports 模块时间显示修复（显示部分）
- [ ] lifewatch 主界面时间显示修复
- [ ] 所有时间显示统一使用 `dateUtils` 函数

### Part 2
- [ ] `goal_journal` PATCH 后 `updated_at` 正确刷新为 UTC ISO 8601
- [ ] 测试验证

### Part 3
- [ ] `plan_doc` PATCH `updated_at` 刷新（如需要）

## Blocked by

- Issue #21 - 前端时间转换工具完善

## 注意事项

1. **后端 API 不做转换**：API 保持 UTC ISO 8601 透传
2. **只改前端组件**：所有时间显示转换在组件层就地完成
3. **goal_journal 修复是后端存储问题**：这是 `updated_at` 自动刷新的 bug，不是时间格式转换
4. **参考审查报告**：`.scratch/utc-timezone-migration/frontend-user-facing-audit.md` 中列出的所有位置
