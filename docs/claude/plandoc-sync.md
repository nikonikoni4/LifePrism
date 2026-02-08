# 计划书 MD 文档同步规则

计划书（PlanDoc）使用 Markdown 文件存储任务列表，通过 `taskpool_service.py` 实现 MD 与数据库的双向同步。

## Todoblock 格式规范

```markdown
<!-- lp:todoblock -->
- [ ] 任务内容 <!-- lp:t-a1b2c3d4 -->
	- [x] 子任务 <!-- lp:t-e5f6g7h8 -->
<!-- /lp:todoblock -->
```

- 支持多个 todoblock，每个 block 独立解析
- 父子关系仅在同一 block 内有效（不跨 block）
- 若 MD 文件无 todoblock，同步时自动创建

## 锚点（Anchor）格式

- 格式：`<!-- lp:t-{uuid[:8]} -->`
- 前缀固定 `t-`，后跟 UUID 前 8 位十六进制字符
- 锚点在任务行末尾，每个任务必须有唯一锚点
- 无锚点的任务在同步时自动生成

## 任务行格式

完整格式：`{Tab缩进}- [{空格或x}] {内容} <!-- lp:t-xxx -->`

解析正则：
```python
r'^(\t*)-\s*\[([ xX])\]\s*(.+?)(?:\s*<!--\s*lp:(t-[a-f0-9]+)\s*-->)?$'
```

示例：
```markdown
- [ ] 根任务 <!-- lp:t-a1b2c3d4 -->
	- [x] 子任务 1 <!-- lp:t-e5f6g7h8 -->
	- [ ] 子任务 2 <!-- lp:t-i9j0k1l2 -->
		- [ ] 孙任务 <!-- lp:t-m3n4o5p6 -->
```

## 缩进与父子关系

- 缩进级别 = Tab 字符数（必须用 Tab，不能用空格）
- 0 个 Tab = 根任务，1 个 Tab = 一级子任务
- 父子关系仅在同一 todoblock 内有效

算法（栈结构）：
1. 遍历任务，弹出栈中所有 level >= 当前 level 的项
2. 栈顶元素的 anchor_id 即为当前任务的父任务
3. 当前任务入栈

## 状态同步规则

### MD → DB（同步时）

| MD Checkbox | 数据库 state | 说明 |
|------------|-------------|------|
| `[ ]` | 保持原状态 | 不改变 pool/scheduled |
| `[ ]` + DB 为 `completed` | `pool` | 清除 `actual_finished_at` |
| `[x]` | `completed` | 设置 `actual_finished_at` |

### DB → MD（回写时）

| 触发条件 | 操作 |
|---------|------|
| `state` 变为 `completed` | `[ ]` → `[x]` |
| `state` 从 `completed` 变为其他 | `[x]` → `[ ]` |
| `content` 变更 | 更新 MD 中的任务内容 |

## 同步流程（sync_plan_doc）

1. 验证计划书存在 → 2. 读取 MD 文件 → 3. 获取所有 todoblock → 4. 解析每个 block 中的任务 → 5. 为无锚点任务生成锚点并写回 MD → 6. 构建父任务映射（每个 block 独立）→ 7. 获取现有任务（数据库）→ 8. 检测待删除任务（DB 有但 MD 无）→ 9. 处理每个任务（存在→更新，不存在→创建）→ 10. 执行数据库操作 → 11. 处理删除（需 confirm_delete=True）→ 12. 保存 MD 文件

参数：
- `dry_run=True`：预检模式，只返回差异不执行
- `confirm_delete=True`：确认删除 DB 中多余的任务

## 任务创建与插入

插入策略（`_insert_todo_to_md`）：
- 有 `parent_anchor_id` → 插入到父任务所在的 block
- 无 `parent_anchor_id` → 插入到第一个 todoblock
- 缩进级别 = 父任务缩进 + 1
- 插入位置 = 父任务的最后一个子任务之后

子任务继承（`create_todo_v2`）：
- 自动继承父任务的 `plan_doc_id` 和 `link_to_goal_id`

## 任务删除

1. 从 MD 删除任务及其所有子任务
2. 级联删除数据库记录

MD 删除算法：
1. 查找锚点所在行，记录缩进级别
2. 删除该行
3. 删除所有缩进级别 > 该行的后续行（子任务）
4. 清理连续的多余空行

## 安全处理（回写前置检查）

- 无 `plan_doc_id` → 跳过 MD 操作
- 无 `source_anchor_id` → 跳过 MD 操作
- 计划书不存在 → 清除关联
- MD 文件不存在 → 跳过 MD 操作
- 锚点不存在 → 跳过 MD 操作

## 文件路径

- 计划书目录：`Path(settings.lifeprism_data_path) / "plan"`
- 文件命名：`{plan_doc_id}.md`

## 关键数据库字段

| 字段 | 说明 |
|------|------|
| `plan_doc_id` | 关联的计划书 ID |
| `source_anchor_id` | MD 锚点 ID（格式：t-xxx） |
| `parent_id` | 父任务 ID |
| `pool_order_index` | 任务池排序（全局顺序） |

## 三数据源架构与同步分析

### 数据源关系

PlanDoc 系统存在三个数据源，以 **MD 文件为中心枢纽**：

```
前端编辑器 (Editor)  ←→  MD 文件 (File)  ←→  数据库 (DB)
```

- **Editor ↔ MD**：编辑器通过 API 读写 MD 文件（`planDocApi.updatePlanDoc` / `getPlanDocDetail`）
- **MD ↔ DB**：后端通过 `taskpool_service` 实现双向同步（`sync_plan_doc` / `update_todo_with_writeback`）
- **Editor 与 DB 不直接交互**，所有数据必须经过 MD 文件中转

### 8 种变更场景分析

三个数据源各自可能发生变更，共 2³ = 8 种组合：

| # | Editor | MD | DB | 场景 | 当前处理 | 状态 |
|---|--------|----|----|------|---------|------|
| 1 | - | - | - | 无变更 | 无需操作 | ✅ |
| 2 | ✓ | - | - | 用户编辑 PlanDoc | 手动保存 / 切换文档自动保存 → MD；MD→DB 需手动点"同步" | ⚠️ |
| 3 | - | ✓ | - | 外部修改 MD 文件 | 无自动检测；需手动刷新编辑器 + 手动同步到 DB | ⚠️ |
| 4 | - | - | ✓ | 任务池操作（勾选/拖拽等） | `update_todo_with_writeback` 自动回写 MD；`triggerAllPlanDocRefreshes` 自动刷新编辑器 | ✅ |
| 5 | ✓ | ✓ | - | 编辑器未保存 + MD 被外部修改 | 编辑器保存会覆盖外部修改；仅用户主动刷新时有冲突对话框 | ❌ |
| 6 | ✓ | - | ✓ | 编辑器未保存 + 任务池操作 | **Save Hook 机制**：操作前 `triggerAllPlanDocSaves` → 执行操作 → `triggerAllPlanDocRefreshes` | ✅ |
| 7 | - | ✓ | ✓ | MD 被外部修改 + 任务池操作 | `triggerAllPlanDocSaves` 将编辑器旧内容覆盖 MD（外部修改丢失）→ DB 更新 → MD 回写 → 编辑器刷新 | ❌ |
| 8 | ✓ | ✓ | ✓ | 三者同时变更 | 无法完全处理，数据丢失风险 | ❌ |

### 各场景详细说明

**场景 2（仅编辑器变更）**：Editor → MD 有保存机制，但 MD → DB 依赖用户手动点击"同步"按钮，非实时。

**场景 3（仅 MD 外部变更）**：系统无文件监听（file watcher），无法感知外部修改。用户必须手动刷新编辑器 + 手动同步。

**场景 5（编辑器 + MD 冲突）**：编辑器保存时直接覆盖 MD 文件，不做 diff 合并。PlanDocListView 的刷新功能有冲突对话框（`hasUnsavedChanges` 检测），但仅在用户主动刷新时触发。

**场景 7（MD 外部修改 + 任务池操作）**：任务池操作走 todo 标准流程：`triggerAllPlanDocSaves` → 编辑器旧内容覆盖 MD（外部修改丢失）→ 后端更新 DB → 后端回写 MD → `triggerAllPlanDocRefreshes` 刷新编辑器。外部修改被编辑器旧内容覆盖。

**场景 8（三者冲突）**：`triggerAllPlanDocSaves` 先将编辑器内容覆盖到 MD（丢失外部修改），然后任务池操作回写 MD（可能覆盖编辑器的部分修改）。

### 设计约束

- **MD 文件是唯一真实数据源**：编辑器和数据库都以 MD 文件为准
- **外部修改不受保护**：系统假设 MD 文件只通过编辑器和后端修改，不考虑外部编辑
- **同步是手动触发的**：MD → DB 方向只在用户点击"同步"时执行，不自动同步

## 前端 PlanDoc 保存 Hook 机制

### 问题
PlanDoc 编辑器、任务池、本地 MD 文件三者可能产生数据冲突（上述场景 6）。

### 解决方案
1. Todo 操作前先触发 PlanDoc 编辑器保存
2. Todo 操作后自动刷新 PlanDoc 编辑器内容

### 数据流

**任务池操作（勾选/创建/删除 todo）**：
```
用户在任务池操作 todo
  → useTaskPoolStore.updateTask/addTask/deleteTask()
  → triggerAllPlanDocSaves()        ← 先保存所有编辑中的 PlanDoc
  → PlanDocListView.silentSave()    ← 静默保存到后端
  → taskPoolApi.updateTodo()        ← 执行 todo 更新
  → 后端更新 DB 和 MD 文件
  → triggerAllPlanDocRefreshes()    ← 刷新所有 PlanDoc 编辑器
  → PlanDocListView.silentRefresh() ← 从后端获取最新内容
```

**同步按钮（TaskPoolView.handleSync）**：
```
用户点击同步按钮
  → triggerPlanDocSave(planDocId)    ← 先保存当前编辑中的 PlanDoc
  → taskPoolApi.syncPlanDoc(dry_run) ← 预检
  → [用户确认删除/保留]
  → taskPoolApi.syncPlanDoc(执行)    ← MD → DB 同步
  → loadTasks()                      ← 刷新任务池列表
  → triggerAllPlanDocRefreshes()     ← 刷新编辑器（后端可能修改了 MD：锚点、系统展示区）
```

### 保存时机

PlanDocListView 的编辑器内容在以下时机写入 MD 文件：

| 时机 | 触发条件 | 实现位置 |
|------|---------|---------|
| 手动保存 | 用户点击保存按钮 / Ctrl+S | `handleSave` |
| 切换文档 | `selectedDoc.id` 变化且有未保存内容 | `useEffect([selectedDoc?.id])` |
| 组件卸载 | 切换标签页（如 plans → daily）且有未保存内容 | `useEffect([], cleanup)` |
| Save Hook | todo 操作前 `triggerAllPlanDocSaves()` 且有未保存内容 | `silentSave` 回调 |

**注意**：Save Hook 回调依赖 PlanDocListView 挂载。当编辑器不在页面上时（如用户在 daily 标签页），回调已被注销，`triggerAllPlanDocSaves()` 不会执行保存。此时依赖"组件卸载时自动保存"确保 MD 文件已是最新。

### 相关文件
- `frontend/apps/goals/hooks/usePlanDocSaveHook.ts` - 保存/刷新 Hook 注册机制
- `frontend/apps/goals/hooks/useTaskPoolStore.ts` - Todo 状态管理（addTask/updateTask/deleteTask 均内置 Save Hook）
- `frontend/apps/goals/components/views/PlanDocListView/PlanDocListView.tsx` - 注册 silentSave/silentRefresh 回调
- `frontend/apps/goals/components/views/TaskPoolView/TaskPoolView.tsx` - 同步按钮逻辑
