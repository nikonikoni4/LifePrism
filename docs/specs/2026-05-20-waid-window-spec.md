---
version: 1.2
created_at: 2026-05-20
updated_at: 2026-05-20
last_updated: 修改计时结束流程，增加活动内容输入对话框
abstract: WAID (What Am I Doing) 浮窗功能规格，定义浮窗的任务管理、计时功能、拖拽排序和状态同步机制
id: waid-window
title: WAID 浮窗功能规格
status: draft
module: floating/waid
sourc_spec: 
related_plan: 
code_scope: frontend/floating/what-am-i-doing, frontend/dialogs/record-activity
contract_refs: lifeprism/server/api/todos_api.py
---

# WAID 浮窗功能规格

## 版本

| 版本 | 更新内容 |
| ---- | -------- |
| 1.2 | 修改计时结束流程，增加活动内容输入对话框 |
| 1.1 | 补充创建任务和 CustomBlock 的详细字段说明 |
| 1.0 | 创建 spec 初稿 |

## Overview

WAID (What Am I Doing) 是一个独立的 Electron 浮窗应用，用于显示用户当前正在进行的任务。浮窗提供任务管理、计时功能、拖拽排序和实时状态同步，帮助用户专注于当前工作并记录时间投入。

**核心价值**：
- 提供始终可见的任务视图，减少上下文切换
- 快速记录任务时间，无需离开当前工作
- 支持任务树形结构，便于管理子任务
- 与主窗口实时同步，保持数据一致性

## Scope

**包含功能**：
- 任务列表显示（支持树形结构）
- 任务 CRUD 操作（创建、编辑、完成、删除）
- 任务计时功能（启动/停止计时器）
- 拖拽排序任务
- 任务折叠/展开
- 与主窗口状态同步
- 窗口自适应高度

**不包含功能**：
- 任务分类管理
- 任务优先级设置
- 任务截止日期管理
- 任务标签管理
- 任务搜索功能

## Core Behavior

### 1. 任务显示逻辑

**数据源**：
- 显示所有 `waid_order IS NOT NULL` 的任务
- 按 `waid_order` 升序排列
- 支持树形结构显示（父子关系）

**显示规则**：
- 每个任务显示：任务名称、计时状态、累计时长
- 树形结构通过缩进和连接线表示层级关系
- 支持折叠/展开子任务
- 已完成任务显示删除线样式

### 2. 任务操作规则

**创建任务**：
- 支持两种创建方式：新建任务、选择现有任务
- 新建任务流程：
  1. 用户点击 "Add" 按钮，选择 "New task"
  2. 输入任务名称并确认
  3. 调用 `safeCreateTodo` 创建任务，自动关联到每日目标
  4. 调用 `WaidAPI.addToWaid` 将任务添加到浮窗
- 默认字段值：
  - `state`: `'scheduled'`（已安排状态）
  - `link_to_goal_id`: `'goal-daily'`（每日目标）
  - `plan_doc_id`: `'每日目标-docs'`（每日目标计划文档）
  - `date`: 今天日期
- PlanDoc 同步机制：
  - 创建前：通知主窗口保存所有 PlanDoc 编辑器内容（防止数据丢失）
  - 创建后：通知主窗口刷新所有 PlanDoc 编辑器（显示最新内容）

**完成任务**：
- 切换任务状态为 `completed`
- 如果任务正在计时，自动停止计时器
- 完成后自动从浮窗移除（清除 `waid_order`）

**删除任务**：
- 从浮窗移除（清除 `waid_order`）
- 不删除任务本身

**编辑任务**：
- 支持双击编辑任务名称
- 编辑时实时同步到主窗口

### 3. 计时功能规则

**计时器状态**：
- 全局互斥：同一时间只能有一个任务在计时
- 计时器状态包括：活动任务ID、开始时间、已过秒数

**计时流程**：
1. 用户点击任务计时按钮启动计时
2. 每秒更新已过时间显示
3. 用户点击停止按钮时：
   - 如果计时 >= 60 秒，弹出活动内容输入对话框
   - 用户在对话框中输入/修改活动内容
   - 用户点击确定后创建 CustomBlock
4. 用户完成任务时：
   - 如果任务正在计时，自动停止计时器
   - 如果计时 >= 60 秒，弹出活动内容输入对话框

**活动内容输入对话框**：
- 对话框 ID：`record-activity`
- 显示信息：
  - 任务名称（只读）
  - 开始时间（HH:MM:SS 格式）
  - 结束时间（HH:MM:SS 格式）
  - 时长（分钟）
- 输入框：多行文本输入框（textarea），默认值为任务名称
- 按钮：只有一个"确定"按钮
- 交互：用户可以修改默认内容，点击确定后创建 CustomBlock

**CustomBlock 创建规则**：
- 触发条件：实际计时 >= 60 秒
- 字段映射：
  - `content`: 用户在对话框中输入的内容（不再是任务名称）
  - `start_time`: 计时开始时间（本地时间格式 `YYYY-MM-DDTHH:MM:SS`）
  - `end_time`: 计时结束时间（本地时间格式 `YYYY-MM-DDTHH:MM:SS`）
  - `duration`: `Math.ceil((end_time - start_time) / 60000)` 分钟
  - `todo_id`: 被计时任务的 ID
  - `color`: 默认 `'#bfdbfe'`（蓝色）
- 时间格式：使用本地时间，不转换为 UTC，不带毫秒

**计时中修改任务**：
- 如果在计时过程中修改了任务名称，会同步更新 ref 中的内容
- 对话框中的默认内容会使用最新的任务名称

**窗口关闭处理**：
- 使用 `navigator.sendBeacon()` 确保请求在窗口关闭时仍能发出
- 窗口关闭时不弹出对话框，直接使用任务名称作为 content
- 同样遵循 >= 60 秒才创建的规则

### 4. 拖拽排序规则

**排序范围**：
- 只能在同级任务间拖拽
- 不能跨层级拖拽

**排序逻辑**：
1. 拖拽开始时记录原始位置
2. 拖拽结束时计算新位置
3. 乐观更新本地状态
4. 调用 API 持久化新顺序
5. 如果持久化失败，回滚到原始状态

**排序持久化**：
- 调用 `PUT /api/v2/todos/waid/reorder` 批量更新
- 按数组顺序赋值 `waid_order` 0, 1, 2...

### 5. 状态同步机制

**数据同步**：
- 监听主窗口发送的 `waid-refresh` 消息
- 收到消息时重新加载任务列表和累计时长

**窗口通信**：
- 使用 Electron IPC 机制
- 浮窗通过 `window.electronAPI` 与主进程通信

## Technical Contract

### 1. 数据库 Schema

**todo_list 表相关字段**：
- `id`: TEXT PRIMARY KEY
- `content`: TEXT NOT NULL
- `state`: TEXT (pool, scheduled, completed)
- `date`: TEXT (YYYY-MM-DD)
- `link_to_goal_id`: TEXT
- `plan_doc_id`: TEXT
- `waid_order`: INTEGER DEFAULT NULL
- `parent_id`: TEXT DEFAULT NULL
- `order_index`: INTEGER

**waid_order 语义**：
- `IS NOT NULL`: 任务在浮窗中显示
- `IS NULL`: 任务不在浮窗中
- 值表示排序顺序（0, 1, 2...）

### 2. API 契约

**获取浮窗任务列表**：
```
GET /api/v2/todos/waid
Response: { items: BackendTodoItem[] }
```

**添加任务到浮窗**：
```
PUT /api/v2/todos/{todo_id}/waid
Request: { waid_order?: number }
Response: { success: boolean, waid_order: number }
```
- 如果未指定 `waid_order`，自动追加到末尾（MAX+1）

**从浮窗移除任务**：
```
DELETE /api/v2/todos/{todo_id}/waid
Response: { success: boolean }
```
- 设置 `waid_order = NULL`

**批量重排序**：
```
PUT /api/v2/todos/waid/reorder
Request: { todo_ids: string[] }
Response: { success: boolean }
```
- 按数组顺序赋值 `waid_order` 0, 1, 2...

**批量获取累计时长**：
```
POST /api/v2/timeline/custom-blocks/batch-duration
Request: { todo_ids: string[], date: string }
Response: { data: Record<string, number> }
```
- 返回每个任务在指定日期的累计分钟数

**创建新任务（点击 Add → New task）**：
```
POST /api/v2/todos
Request: {
    content: string;                    // 任务名称（必填）
    state?: string;                     // 任务状态，默认 'scheduled'
    date?: string | null;               // 任务日期（YYYY-MM-DD），默认今天
    color?: string;                     // 任务颜色
    link_to_goal_id?: string | null;    // 关联目标ID，默认 'goal-daily'
    plan_doc_id?: string | null;        // 关联计划文档ID，默认 '每日目标-docs'
    parent_id?: string | null;          // 父任务ID
    expected_finished_at?: string | null; // 预期完成时间
    pool_order_index?: number | null;   // 任务池排序索引
}
Response: { item: BackendTodoItem }
```

**WAID 浮窗创建任务的默认字段值**：
- `content`: 用户输入的任务名称
- `state`: `'scheduled'`（已安排状态）
- `date`: 今天日期（`YYYY-MM-DD` 格式）
- `link_to_goal_id`: `'goal-daily'`（每日目标）
- `plan_doc_id`: `'每日目标-docs'`（每日目标计划文档）

**创建 CustomBlock（计时结束时）**：
```
POST /api/v2/timeline/custom-blocks
Request: {
    content: string;          // 活动内容描述（任务名称）
    start_time: string;       // 开始时间（YYYY-MM-DDTHH:MM:SS 本地时间格式）
    end_time: string;         // 结束时间（YYYY-MM-DDTHH:MM:SS 本地时间格式）
    duration: number;         // 持续时长（分钟，向上取整）
    category_id?: string;     // 主分类ID（可选）
    sub_category_id?: string; // 子分类ID（可选）
    todo_id?: string;         // 关联的待办事项ID
    color?: string;           // 活动颜色，默认 '#bfdbfe'（蓝色）
}
Response: { data: UserCustomBlock }
```

**CustomBlock 创建规则**：
- 仅在计时 >= 60 秒时才创建
- 正常停止计时时：
  - 弹出活动内容输入对话框
  - `content`: 取自用户在对话框中输入的内容
- 窗口关闭时：
  - 不弹出对话框
  - `content`: 取自任务的 `content` 字段（任务名称）
- `start_time` / `end_time`: 使用本地时间格式（非 UTC），格式为 `YYYY-MM-DDTHH:MM:SS`
- `duration`: 计算方式为 `Math.ceil((end_time - start_time) / 60000)` 分钟
- `todo_id`: 关联到被计时的任务 ID
- `color`: 默认使用蓝色 `#bfdbfe`

**窗口关闭时的计时保存**：
- 使用 `navigator.sendBeacon()` 确保请求在窗口关闭时仍能发出
- 不弹出对话框，直接使用任务名称作为 content
- 同样遵循 >= 60 秒才创建的规则

### 3. Electron IPC 契约

**浮窗窗口管理**：
- `resizeFloatingWindow(windowId, { width, height })`: 调整浮窗大小
- `getFloatingWindowSize(windowId)`: 获取浮窗当前尺寸
- `openDialogWindow(dialogId)`: 打开对话框窗口

**消息通信**：
- `onMessage(channel, callback)`: 监听消息
- `removeMessageListener(channel, handler)`: 移除监听器

**消息通道**：
- `waid-refresh`: 主窗口通知浮窗刷新数据
- `activity-recorded`: 活动内容输入对话框返回用户输入的内容

### 4. 前端组件结构

**主组件**：`WhatAmIDoingFloat`
- 管理任务列表状态
- 处理窗口自适应高度
- 协调子组件交互

**子组件**：
- `WaidTodoItem`: 单个任务项组件
- `AddTaskMenu`: 添加任务菜单组件

**对话框组件**：
- `RecordActivityDialog`: 活动内容输入对话框（位于 `frontend/dialogs/record-activity/`）

**Hook**：
- `useWaidTimer`: 计时器状态管理 Hook

**API 层**：
- `WaidAPI`: 浮窗专用 API 封装
- `safeTodoOps`: 安全的任务操作封装

## Interaction / UX Notes

### 1. 窗口行为

**窗口特性**：
- 始终置顶显示
- 无边框窗口
- 标题栏可拖拽移动
- 内容区域可滚动
- 高度自适应（120px - 600px）

**自适应逻辑**：
- 监听内容区域高度变化
- 计算总高度 = 内容高度 + 标题栏高度 + 添加按钮高度 + 内边距
- 限制在最小/最大高度范围内
- 获取当前窗口宽度并明确传入，避免副屏幕宽度 bug

### 2. 交互设计

**任务项交互**：
- 悬停显示操作按钮（计时、更多菜单）
- 双击任务名称进入编辑模式
- 点击复选框切换完成状态
- 点击折叠箭头展开/折叠子任务

**计时器交互**：
- 计时按钮：点击启动/停止计时
- 计时状态：绿色脉冲点 + 已过时间
- 累计时长：显示在任务右侧

**拖拽交互**：
- 拖拽手柄：6个小圆点图标
- 拖拽时任务半透明
- 拖拽结束时平滑过渡

### 3. 视觉设计

**颜色方案**：
- 背景：深灰色 (#1e1e1e)
- 文字：白色/半透明白色
- 强调色：翠绿色渐变 (#10b981 → #14b8a6)
- 计时状态：绿色 (#22c55e)
- 已完成任务：半透明白色 + 删除线

**布局**：
- 标题栏：32px 高度，翠绿色渐变背景
- 内容区域：可滚动，垂直排列任务项
- 底部区域：添加按钮，分隔线

## Acceptance Notes

### 1. 功能验收

**任务管理**：
- ✅ 能够创建新任务
- ✅ 能够选择现有任务添加到浮窗
- ✅ 能够完成任务并自动移除
- ✅ 能够编辑任务名称
- ✅ 能够删除任务（从浮窗移除）

**计时功能**：
- ✅ 能够启动/停止计时器
- ✅ 计时器状态正确显示
- ✅ 停止时正确创建 CustomBlock
- ✅ 窗口关闭时数据不丢失

**排序功能**：
- ✅ 能够拖拽排序任务
- ✅ 排序结果正确持久化
- ✅ 排序失败时正确回滚

**同步功能**：
- ✅ 能够接收主窗口刷新消息
- ✅ 数据变更实时同步到主窗口

### 2. 性能验收

**响应性**：
- 任务列表加载 < 500ms
- 计时器更新延迟 < 100ms
- 拖拽操作流畅，无卡顿

**资源占用**：
- 内存占用 < 100MB
- CPU 占用 < 5%（空闲时）

### 3. 兼容性验收

**平台支持**：
- Windows 10/11
- macOS 10.15+
- Linux (Ubuntu 20.04+)

**Electron 版本**：
- Electron 20+

## Out of Spec

以下内容不在本 spec 中长期维护：

### 1. 实现细节

- 具体的组件实现代码
- TypeScript 类型定义
- CSS 样式细节
- 动画过渡效果

### 2. 平台特定问题

- Electron 在副屏幕的宽度 bug（已知问题，有 workaround）
- Windows 平台窗口置顶问题（已修复）

### 3. 未来功能扩展

- 任务分类管理
- 任务优先级设置
- 任务截止日期
- 任务标签系统
- 任务搜索和过滤
- 任务统计和报告

### 4. 集成细节

- 与主窗口的具体通信协议
- 数据库迁移脚本
- 部署和打包配置

---

**文档维护说明**：
- 本文档描述 WAID 浮窗的功能规格和业务规则
- 实现细节请参考代码库
- 平台特定问题请参考 `docs/temp/bugs/` 目录
- 功能扩展请创建新的 spec 文档