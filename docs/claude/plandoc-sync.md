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
| `[x]` | `completed` | 设置 `actual_finished_at` |

**重要限制**：同步时只能 `[ ]` → `[x]`，不能 `[x]` → `[ ]`

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

## 前端 PlanDoc 保存 Hook 机制

### 问题
PlanDoc 编辑器、任务池、本地 MD 文件三者可能产生数据冲突。

### 解决方案
1. Todo 操作前先触发 PlanDoc 编辑器保存
2. Todo 操作后自动刷新 PlanDoc 编辑器内容

### 数据流

```
用户在任务池勾选 todo
  → useTaskPoolStore.updateTask()
  → triggerAllPlanDocSaves()        ← 先保存所有编辑中的 PlanDoc
  → PlanDocListView.silentSave()    ← 静默保存到后端
  → taskPoolApi.updateTodo()        ← 执行 todo 更新
  → 后端更新 DB 和 MD 文件
  → triggerAllPlanDocRefreshes()    ← 刷新所有 PlanDoc 编辑器
  → PlanDocListView.silentRefresh() ← 从后端获取最新内容
```

### 相关文件
- `frontend/apps/goals/hooks/usePlanDocSaveHook.ts` - 保存/刷新 Hook 注册机制
- `frontend/apps/goals/hooks/useTaskPoolStore.ts` - Todo 状态管理
- `frontend/apps/goals/components/views/PlanDocListView/PlanDocListView.tsx` - 注册回调
