# Goals 旧版本移除影响分析

## ✅ 迁移完成

**完成时间**: 2026-02-04
**Commit**: dcd12cb (frontend), 060a3bd (backend)

所有 Goals V1 代码已成功迁移到 V2，旧代码已完全移除。

---

## 迁移总结

### 后端迁移 (commit 060a3bd)
- ✅ 删除旧 API 端点 `/api/v2/todo`
- ✅ 删除 `todo_service.py` (580 行)
- ✅ 删除 `todo_api.py` (297 行)
- ✅ 删除 18 个 V1 schema 类
- ✅ 删除数据库表 `sub_todo_list`, `task_pool_folder`
- ✅ 新 API 端点：`/api/v2/goal`, `/api/v2/todos`, `/api/v2/taskpool`

### 前端迁移 (commit dcd12cb)

#### 1. TodoListWidget (首页待办组件)
**文件**: `frontend/page/home/components/TodoListWidget.tsx`

**修改内容**:
- ✅ 导入更新：`goalsV2/types/todo`, `goalsV2/apis/taskPool`
- ✅ API 调用：`taskPoolApi.fetchTaskPool()` + 日期过滤
- ✅ 状态判断：`item.completed` → `item.state === 'completed'`
- ✅ 跨日计算：比较 `scheduledDate` 和 `expectedFinishAt`
- ✅ 导航跳转：跳转到 `goalsV2` 而不是 `goals`

#### 2. CategoryMapCacheTab (分类缓存管理)
**文件**: `frontend/page/category/components/CategoryMapCacheTab.tsx`

**修改内容**:
- ✅ 导入更新：`goalsV2/apis/goal`, `goalsV2/types/entities`
- ✅ API 调用：`goalsV2Api.getGoals()` + 过滤有分类的目标
- ✅ 字段重命名：`goal.name` → `goal.title`

#### 3. Timeline (时间轴页面)
**文件**: `frontend/page/timeline/Timeline.tsx`

**修改内容**:
- ✅ 导入更新：`goalsV2/apis/taskPool`
- ✅ API 调用：`taskPoolApi.fetchTaskPool()` + 日期过滤

#### 4. App.tsx (主应用)
**文件**: `frontend/App.tsx`

**修改内容**:
- ✅ 删除旧 GoalsPage 导入
- ✅ 删除旧路由 `{currentPage === 'goals' && <GoalsPage />}`

#### 5. Sidebar (侧边栏)
**文件**: `frontend/components/Sidebar.tsx`

**修改内容**:
- ✅ 删除注释掉的旧路由代码

#### 6. 删除旧文件夹
**位置**: `frontend/page/goals/`

**删除文件** (18 个文件，10,565 行代码):
- ✅ `GoalsPage.tsx`
- ✅ `api.ts`
- ✅ `types.ts`
- ✅ `index.ts`
- ✅ `components/BeingTabView.tsx`
- ✅ `components/CategorySelectionModal.tsx`
- ✅ `components/DateTreeSelector.tsx`
- ✅ `components/GoalDetailView.tsx`
- ✅ `components/GoalTabView.tsx`
- ✅ `components/PlanTabView.tsx`
- ✅ `components/RewardTabView.tsx`
- ✅ `components/TaskDetailPanel.tsx`
- ✅ `components/TaskPoolTree.tsx`
- ✅ `components/TodoTabView.tsx`
- ✅ `components/WeekDayTreeSelector.tsx`
- ✅ `components/WhoAmITab.tsx`
- ✅ `components/WhoIWantToBeTab.tsx`
- ✅ `components/WhoWasITab.tsx`

---

## 核心变化

### 类型系统变化

#### 旧版 V1 TodoItem
```typescript
{
  state: 'active' | 'completed' | 'inactive',
  completed: boolean,  // ❌ 已移除
  linkToGoalId: string | null,
  date: string | null,
  crossDay: boolean  // ❌ 已移除
}
```

#### 新版 V2 TodoItem
```typescript
{
  state: 'pool' | 'scheduled' | 'completed' | 'shelved',
  goalId: string | null,  // ✅ 重命名
  scheduledDate: string | null,  // ✅ 重命名
  expectedFinishAt: string | null,  // ✅ 新增
  // 跨日通过比较日期计算
}
```

### API 端点变化

| 功能 | V1 端点 | V2 端点 |
|------|---------|---------|
| 获取待办 | `GET /api/v2/todo?date=xxx` | `GET /api/v2/taskpool?state=scheduled` + 前端过滤 |
| 获取目标 | `GET /api/v2/goal/with-category` | `GET /api/v2/goal?status=active` + 前端过滤 |
| 创建待办 | `POST /api/v2/todo` | `POST /api/v2/todos` |
| 更新待办 | `PUT /api/v2/todo/{id}` | `PUT /api/v2/todos/{id}` |

---

## 验证结果

### 构建测试
- ✅ TypeScript 编译成功
- ✅ 无类型错误
- ✅ 无导入错误
- ✅ 构建输出正常 (19.04s)

### 代码统计
- **删除**: 10,565 行旧代码
- **新增**: 24 行迁移代码
- **净减少**: 10,541 行代码

---

## 后续工作

### 可选优化
1. **Daily Focus 功能**: V2 暂未实现 `dailyFocusContent`，可考虑添加独立端点
2. **性能优化**: 考虑在后端添加按日期过滤的参数，减少前端过滤开销
3. **重命名**: 将 `goalsV2` 重命名为 `goals`（移除 V2 后缀）

### 测试建议
- [ ] 手动测试首页待办显示
- [ ] 测试分类缓存管理功能
- [ ] 测试时间轴待办绑定
- [ ] 测试跨日任务显示
- [ ] 测试完成状态切换

---

## 参考文档

- 后端迁移 commit: `060a3bd`
- 前端迁移 commit: `dcd12cb`
- 迁移计划: `C:\Users\15535\.claude\plans\noble-tumbling-snowflake.md`
