# 001修改

日期： 2026-1-31 12:00
任务：新增组件和交互
主要修改文件位置：frontend\page\goalsV2

## 完成情况

**完成日期：** 2026-1-31

### 已修改的文件

| 文件路径 | 修改内容 |
|---------|---------|
| `frontend/page/goalsV2/components/shared/components/todoItem/TodoItemDetailed.tsx` | 主组件修改 |
| `frontend/my-ui-kit/ui-kit/todoItem/TodoItemDetailed.tsx` | UI Kit 版本同步修改 |

### 新增的 Props

```typescript
interface TodoItemDetailedProps {
    // ... 原有 props ...

    // 新增
    onAddChild?: (parentId: number) => void;  // 添加子项回调
    goalName?: string;                         // Goal 名称（用于显示标签）
    planName?: string;                         // Plan 名称（用于显示标签）
}
```

### 新增的功能

1. **+ 添加子项按钮**
   - 位置：Header 右侧 hover 操作区（调色盘按钮之前）
   - 图标：`Plus` (lucide-react)
   - 点击触发 `onAddChild(todo.id)` 回调

2. **Goal 标签**
   - 位置：标签区第一个位置
   - 样式：紫色背景 (`bg-purple-50 text-purple-600`)
   - 图标：`Target` (lucide-react)
   - 显示条件：`goalName` prop 有值时显示

3. **Plan 标签**
   - 位置：标签区第二个位置
   - 样式：蓝色背景 (`bg-blue-50 text-blue-600`)
   - 图标：`FileText` (lucide-react)
   - 显示条件：`planName` 有值，或 `sourceType === 'plan_doc' && showSource`

4. **标签顺序调整**
   - 新顺序：Goal → Plan → delayStatus
   - 原顺序：delayStatus → Plan

---

## 需要同步修改的地方

以下文件使用了 `TodoItemDetailed` 组件，需要根据实际需求传入新的 props：

### 1. TodoItemTreeDetailed 组件

**文件路径：**
- `frontend/page/goalsV2/components/shared/components/todoItem/TodoItemTreeDetailed.tsx`
- `frontend/my-ui-kit/ui-kit/todoItem/TodoItemTreeDetailed.tsx`

**需要修改：**
- 在 `TodoItemNodeProps` 接口中添加新 props
- 在 `TodoItemTreeDetailedProps` 接口中添加新 props（`onAddChild`, `goalName`, `planName` 或获取方式）
- 将新 props 传递给内部的 `<TodoItemDetailed>` 组件

**示例修改：**
```tsx
// TodoItemTreeDetailedProps 新增
interface TodoItemTreeDetailedProps {
    // ... 原有 props ...
    onAddChild?: (parentId: number) => void;
    getGoalName?: (goalId: string | null) => string | undefined;
    getPlanName?: (planDocId: string | null) => string | undefined;
}

// 传递给 TodoItemDetailed
<TodoItemDetailed
    todo={item}
    onAddChild={onAddChild}
    goalName={getGoalName?.(item.goalId)}
    planName={getPlanName?.(item.planDocId)}
    // ... 其他 props
/>
```

### 2. DragDropTestPage 测试页面

**文件路径：**
- `frontend/page/tempDisplay/DragDropTestPage.tsx`

**需要修改：**
- 如需测试新功能，添加 `onAddChild` 回调和 `goalName`/`planName` 数据
- 测试数据 `createDailyFocusTasks()` 可添加 goal 关联

### 3. 实际使用页面（待确认）

根据项目架构，以下页面可能需要集成新功能：

| 页面 | 说明 | 需要的修改 |
|-----|------|-----------|
| 每日聚焦页面 | 使用 TodoItemTreeDetailed | 传入 `onAddChild` 和 goal/plan 名称获取函数 |
| 目标详情页面 | 可能使用 TodoItemDetailed | 同上 |

### 4. 数据层支持

为了显示 Goal 和 Plan 名称，可能需要：

1. **Goals 数据获取**
   - 确保有 `goalId` → `goalName` 的映射
   - 可通过 context 或 props 传递

2. **PlanDoc 数据获取**
   - 确保有 `planDocId` → `planName` 的映射
   - 可通过 context 或 props 传递

---

## 使用示例

```tsx
import { TodoItemDetailed } from './TodoItemDetailed';

// 基础使用（不启用新功能）
<TodoItemDetailed
    todo={todo}
    onUpdate={handleUpdate}
    onDelete={handleDelete}
/>

// 完整使用（启用所有新功能）
<TodoItemDetailed
    todo={todo}
    onUpdate={handleUpdate}
    onDelete={handleDelete}
    onAddChild={(parentId) => {
        // 创建子任务逻辑
        console.log('Add child to:', parentId);
    }}
    goalName="学习目标"
    planName="周计划"
/>
```

---

## 当前的内容

1. **顶部标题栏 (Header)**
    *   **左侧：** 包含一个六点式的**拖拽手柄**和任务状态的**圆形复选框**。
    *   **中间：** 任务标题文字（如"验证码逻辑"）。
    *   **右侧：** 包含三个操作图标：**收起/展开箭头**、**调色盘（主题/分类）**和**垃圾桶（删除）**。
2. **状态与标签区 (Info & Tags)**
    *   位于标题下方，展示了任务的时间轴信息：
        *   **开始时间：** 带有日历图标。
        *   **预期时间：** 带有秒表图标。
    *   **胶囊标签：** 右侧有两个色彩鲜明的标签，分别是"今日截止"（橙色，起警示作用）和"Plan"（蓝色，表示任务类型或计划）。
3. **内容/备注区 (Main Content)** （ 展开后显示 ）
    *   中间是一个明显的**输入框区域**。
    *   上方带有标题"拖延/未完成原因"，并附带信息图标。
    *   输入框中有占位符文字，提示用户记录原因以便复盘。
4. **底部辅助信息 (Footer)**（ 展开后显示 ）
    *   卡片最底端以简洁的图标和文字再次确认了**开始日期**和**预期结束时间**（或日期）。

### 目表内容

- 新添加元素：
    1. **顶部标题栏 (Header)**：
        *  右侧增加一个+按钮用于添加该todo的子项
    2. **状态与标签区 (Info & Tags)**：
        *  胶囊标签增加一个Goal信息

- 完整组成元素：

    1. **顶部标题栏 (Header)**
        *   **左侧：** 包含一个六点式的**拖拽手柄**和任务状态的**圆形复选框**。
        *   **中间：** 任务标题文字（如"验证码逻辑"）。
        *   **右侧：** 包含四个操作图标：**收起/展开箭头**、**调色盘（主题/分类）**、**+添加子项按钮** 和**垃圾桶（删除）**。
    2. **状态与标签区 (Info & Tags)**
        *   位于标题下方，展示了任务的时间轴信息：
            *   **开始时间：** 带有日历图标。
            *   **预期时间：** 带有秒表图标。
        *   **胶囊标签：** 右侧有三个色彩鲜明的标签（注意顺序），1. **goal标签**，表示该目标所属的goal 2. **plan标签**，表示目标所属的任务书，3. **delayStatus**任务完成时间情况的标签
    3. **内容/备注区 (Main Content)** （ 展开后显示 ）
        *   中间是一个明显的**输入框区域**。
        *   上方带有标题"拖延/未完成原因"，并附带信息图标。
        *   输入框中有占位符文字，提示用户记录原因以便复盘。
    4. **底部辅助信息 (Footer)**（ 展开后显示 ）
        *   卡片最底端以简洁的图标和文字再次确认了**开始日期**和**预期结束时间**（或日期）。


### 新增交互

1. 点击**底部辅助信息 (Footer)**的日期，可以选择开始和预期结束时间
2. 点击+，可以添加子项


# 002修改

日期： 2026-1-31 12:27
任务：完成001修改的附加修改
相关内容位置：见001修改-完成情况-需要同步修改的地方

## 完成情况（AI编写）

**完成日期：** 2026-1-31

### 已修改的文件

| 文件路径 | 修改内容 |
|---------|---------|
| `frontend/page/goalsV2/components/shared/components/todoItem/TodoItemTreeDetailed.tsx` | 新增 props 传递支持 |
| `frontend/my-ui-kit/ui-kit/todoItem/TodoItemTreeDetailed.tsx` | UI Kit 版本同步修改 |
| `frontend/page/tempDisplay/DragDropTestPage.tsx` | 测试页面添加新功能测试 |

### TodoItemTreeDetailed 新增的 Props

```typescript
interface TodoItemTreeDetailedProps {
    // ... 原有 props ...

    // 新增
    onAddChild?: (parentId: number) => void;
    getGoalName?: (goalId: string | null) => string | undefined;
    getPlanName?: (planDocId: string | null) => string | undefined;
}
```

### TodoItemNodeProps 新增的 Props

```typescript
interface TodoItemNodeProps {
    // ... 原有 props ...

    // 新增
    onAddChild?: (parentId: number) => void;
    goalName?: string;
    planName?: string;
}
```

### 修改说明

1. **TodoItemTreeDetailedProps 接口**
   - 新增 `onAddChild` 回调，用于添加子项
   - 新增 `getGoalName` 函数，根据 goalId 获取 Goal 名称
   - 新增 `getPlanName` 函数，根据 planDocId 获取 Plan 名称

2. **TodoItemNodeProps 接口**
   - 新增 `onAddChild` 回调，直接传递给 TodoItemDetailed
   - 新增 `goalName` 和 `planName`，由父组件通过 getter 函数计算后传入

3. **renderItems 函数**
   - 在递归渲染时，调用 `getGoalName?.(item.goalId)` 和 `getPlanName?.(item.planDocId)` 获取名称
   - 将 `onAddChild`、`goalName`、`planName` 传递给 TodoItemNodeDetailed

4. **DragDropTestPage 测试页面**
   - 添加 mock 数据 `goalsMap` 和 `plansMap`
   - 实现 `getGoalName` 和 `getPlanName` 函数
   - 实现 `handleAddChild` 回调，支持添加子任务
   - 更新测试数据，为部分任务添加 `goalId`
   - 将新 props 传递给 `TodoItemTreeDetailed` 组件

### 使用示例

```tsx
// 在使用 TodoItemTreeDetailed 的页面中
const goalsMap = { 'goal-1': '学习目标', 'goal-2': '工作目标' };
const plansMap = { '1': '周计划 A', '2': '周计划 B' };

<TodoItemTreeDetailed
    items={tasks}
    onUpdate={handleUpdate}
    onDelete={handleDelete}
    onAddChild={(parentId) => {
        // 创建子任务逻辑
        console.log('Add child to:', parentId);
    }}
    getGoalName={(goalId) => goalId ? goalsMap[goalId] : undefined}
    getPlanName={(planDocId) => planDocId ? plansMap[planDocId] : undefined}
/>
```