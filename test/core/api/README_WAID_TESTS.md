# WAID API 测试文档

## 概述

本测试套件验证 WAID (What Am I Doing) 浮窗的所有 API 功能，确保前端和后端的数据交互符合预期。

## 测试文件

- `test_waid_api.py` - WAID 浮窗 API 完整测试套件

## 测试覆盖的 API 端点

| 端点 | 方法 | 描述 |
|------|------|------|
| `/api/v2/todos` | POST | 创建任务（WAID 浮窗场景） |
| `/api/v2/todos/waid` | GET | 获取 WAID 浮窗任务列表 |
| `/api/v2/todos/{todo_id}/waid` | PUT | 添加任务到 WAID 浮窗 |
| `/api/v2/todos/{todo_id}/waid` | DELETE | 从 WAID 浮窗移除任务 |
| `/api/v2/todos/waid/reorder` | PUT | WAID 浮窗任务重排序 |
| `/api/v2/todos/{todo_id}` | PUT | 更新任务状态 |

## 前端真实请求数据

### 创建任务（来自 WhatAmIDoingFloat.tsx）

```typescript
// 前端发送的真实请求数据
{
  content: "任务内容",
  state: "scheduled",
  date: "2026-04-20",  // getTodayStr() 返回 YYYY-MM-DD 格式
  link_to_goal_id: "goal-daily",
  plan_doc_id: "每日目标-docs"
}
```

### 关键字段说明

- `content`: 任务内容（必需）
- `state`: 任务状态，WAID 浮窗固定为 `"scheduled"`
- `date`: 日期，WAID 浮窗固定为今天（YYYY-MM-DD 格式）
- `link_to_goal_id`: 关联的目标 ID，WAID 浮窗固定为 `"goal-daily"`
- `plan_doc_id`: 关联的计划书 ID，WAID 浮窗固定为 `"每日目标-docs"`

## 测试用例

### 1. test_create_waid_todo_with_daily_goal
**目的**: 验证从 WAID 浮窗创建任务时，所有字段都正确保存

**验证点**:
- 任务创建成功（状态码 200）
- 返回的任务包含所有字段
- `link_to_goal_id` 正确设置为 `"goal-daily"`
- `plan_doc_id` 正确设置为 `"每日目标-docs"`
- `state` 为 `"scheduled"`
- `date` 为今天

### 2. test_create_waid_todo_without_goal
**目的**: 验证创建任务时不关联目标的兼容性

**验证点**:
- 任务创建成功
- `link_to_goal_id` 和 `plan_doc_id` 为 `null`

### 3. test_get_waid_todos_empty
**目的**: 验证获取空的 WAID 浮窗任务列表

**验证点**:
- 返回空列表
- 响应结构正确

### 4. test_add_todo_to_waid
**目的**: 验证添加任务到 WAID 浮窗

**验证点**:
- 添加成功
- 任务出现在 WAID 列表中
- `waid_order` 字段正确设置

### 5. test_remove_todo_from_waid
**目的**: 验证从 WAID 浮窗移除任务

**验证点**:
- 移除成功
- 任务不在 WAID 列表中
- 任务本身未被删除

### 6. test_reorder_waid_todos
**目的**: 验证 WAID 浮窗任务重排序

**验证点**:
- 重排序成功
- 任务顺序与请求一致

### 7. test_create_waid_todo_with_invalid_goal_id
**目的**: 验证使用不存在的 goal_id 时的行为

**验证点**:
- 任务创建成功（外键约束未启用）
- 不会抛出错误

### 8. test_waid_todo_state_transition
**目的**: 验证任务状态转换（scheduled → completed）

**验证点**:
- 状态更新成功
- `actual_finished_at` 字段自动设置

### 9. test_waid_todo_date_format_validation
**目的**: 验证日期格式（YYYY-MM-DD）

**验证点**:
- 日期格式正确保存
- 符合后端要求

### 10. test_waid_integration_workflow
**目的**: 验证完整的 WAID 工作流程

**流程**:
1. 创建任务（自动关联每日目标）
2. 添加到 WAID 浮窗
3. 查看 WAID 任务列表
4. 完成任务
5. 从 WAID 移除

## 运行测试

```bash
# 运行所有 WAID 测试
pytest test/core/api/test_waid_api.py -v

# 运行单个测试
pytest test/core/api/test_waid_api.py::test_create_waid_todo_with_daily_goal -v

# 运行测试并显示详细输出
pytest test/core/api/test_waid_api.py -v --tb=short
```

## 测试结果

✅ **所有 10 个测试用例通过**

```
test_create_waid_todo_with_daily_goal PASSED
test_create_waid_todo_without_goal PASSED
test_get_waid_todos_empty PASSED
test_add_todo_to_waid PASSED
test_remove_todo_from_waid PASSED
test_reorder_waid_todos PASSED
test_create_waid_todo_with_invalid_goal_id PASSED
test_waid_todo_state_transition PASSED
test_waid_todo_date_format_validation PASSED
test_waid_integration_workflow PASSED
```

## 已知警告

测试过程中会出现以下警告，这是预期行为：

```
WARNING: 插入失败：MD 文件不存在 每日目标-docs
WARNING: 回写失败：MD 文件不存在 每日目标-docs
```

**原因**: "每日目标"是虚拟的 plan_doc，不需要实际的 MD 文件。这不影响功能，任务仍然能成功创建和更新。

## 数据清理

测试使用 `clean_test_data` fixture 自动清理测试数据：
- 所有测试任务的 `content` 以 `[TEST]` 开头
- 测试结束后自动从 `todo_list` 表中删除

## 相关文件

- **前端**: `frontend/floating/what-am-i-doing/WhatAmIDoingFloat.tsx`
- **后端 API**: `lifeprism/server/api/todos_api.py`
- **数据初始化**: `lifeprism/repository/data_initializer.py`
- **Schema**: `lifeprism/server/schemas/todo_schemas.py`

## 注意事项

1. **日期格式**: 必须使用 `YYYY-MM-DD` 格式
2. **ID 格式**: 
   - goal_id: `goal-{identifier}`
   - plan_doc_id: 支持中文字符
   - todo_id: `t-{uuid[:8]}`
3. **外键约束**: SQLite 默认不启用外键约束，因此可以插入不存在的 goal_id
4. **MD 文件**: 每日目标不需要 MD 文件，警告可以忽略
