# 目标管理系统

> 版本: v2.0 | 状态: 重构中 | 更新: 2026-01-31

## 模块定位

承诺 → **目标** → 计划书 → 任务池 → 每日任务

## 文档索引

| 文档 | 描述 |
|------|------|
| [目标视图](目标视图.md) | 目标列表 + 计划书关联 |
| [计划书视图](计划书视图.md) | 计划书编辑 + 任务解析 |
| [任务池视图](任务池视图.md) | 未分配任务管理 |
| [任务分配视图](任务分配视图.md) | 任务池 + 日历拖拽分配 |
| [每日任务视图](每日任务视图.md) | 当日任务执行 |

---

## 整体布局

系统采用"顶部胶囊导航 + 双面板"布局模式。

### 单栏模式
```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              顶部胶囊导航栏                                   │
│   ┌─────────┬─────────┬─────────┬─────────┬─────────┐                       │
│   │  目标   │  计划书  │  任务池  │ 任务分配 │ 每日任务 │    ◀ ▶ 切换按钮     │
│   └─────────┴─────────┴─────────┴─────────┴─────────┘                       │
├─────────────────────────────────────────────────────────────────────────────┤
│  ┌────────────────────────────────────────────────────────────┐             │
│  │                       当前视图 (主面板)                      │             │
│  └────────────────────────────────────────────────────────────┘             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 双栏模式
```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              顶部胶囊导航栏                                   │
│   ┌───────────┬───────────┬───────────┬───────────┐                         │
│   │ 目标—计划 │ 计划—任务 │ 任务—日历 │ 日历—每日 │    ◀ ▶ 切换按钮         │
│   └───────────┴───────────┴───────────┴───────────┘                         │
├─────────────────────────────────────────────────────────────────────────────┤
│  ┌────────────────────────────┐   ┌────────────────────────────┐           │
│  │         左侧面板            │   │         右侧面板            │           │
│  │         (主视图)            │   │        (关联视图)           │           │
│  └────────────────────────────┘   └────────────────────────────┘           │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 视图组合（双栏模式）

| 组合 | 左侧面板 | 右侧面板 | 核心交互 |
|:---|:---|:---|:---|
| 组合 1 | 目标列表 | 计划书 | 点击目标 → 右侧显示关联计划书 |
| 组合 2 | 计划书 | 任务池 | 编辑计划书 → 任务解析至右侧 |
| 组合 3 | 任务池 | 日历分配 | 从左侧拖拽任务 → 放到日历日期 |
| 组合 4 | 日历 | 每日任务 | 点击日期 → 右侧显示该日任务 |

### 响应式规则

| 屏幕宽度 | 布局方案 |
|:---|:---|
| > 1200px | 双栏布局，左右各 50% |
| 768px - 1200px | 双栏布局，左 40%，右 60% |
| < 768px | 强制单栏布局 |

---

## 数据模型

### Goal（目标）

```typescript
interface Goal {
  id: string;
  name: string;
  description?: string;
  status: 'active' | 'completed' | 'archived';
  createdAt: string;
  updatedAt: string;
}
```

### PlanDoc（计划书）

```typescript
interface PlanDoc {
  id: string;
  goalId: string;           // 关联目标
  name: string;
  content: string;          // Markdown 内容
  status: 'draft' | 'active' | 'completed';
  createdAt: string;
  updatedAt: string;
}
```

### TodoItem（任务）

```typescript
interface TodoItem {
  id: number;
  title: string;
  completed: boolean;

  // 关联
  goalId?: string;
  planDocId?: string;
  parentId?: number;        // 父任务ID

  // 时间
  scheduledDate?: string;   // 安排日期 (YYYY-MM-DD)
  startDate?: string;
  dueDate?: string;

  // 状态
  delayReason?: string;     // 拖延原因

  createdAt: string;
  updatedAt: string;
}
```

---

## 状态流转

### TodoItem 状态

```
pending ──完成──> completed
    │
    └──安排日期──> scheduled ──完成──> completed
```

### Goal 状态

```
active ──所有计划书完成──> completed
   │
   └──手动归档──> archived
```

---

## 级联行为规则

| 触发操作 | 级联行为 |
|:---|:---|
| 删除 Goal | 关联的 PlanDoc 和 TodoItem 一并删除 |
| 删除 PlanDoc | 关联的 TodoItem 一并删除 |
| 完成 TodoItem | 检查父任务是否可自动完成 |
| 删除父 TodoItem | 子任务一并删除 |

---

## 后端架构

### 代码位置

- 前端: `frontend/page/goalsV2/`
- 后端 API: `lifeprism/server/api/goal_api.py`
- 后端 Service: `lifeprism/server/services/goal_service.py`
- 数据 Provider: `lifeprism/server/providers/goal_provider.py`

### 后端分层

```
API Layer (goal_api.py)
    ↓
Service Layer (goal_service.py)
    ↓
Provider Layer (goal_provider.py)
    ↓
Database (SQLite)
```

### 开发规范

1. 在 `lifeprism/config/database.py` 完成数据表配置
2. 在 `lifeprism/server/providers/` 创建数据提供类，继承 `LWBaseDataProvider`
3. 在 `lifeprism/server/schemas/` 编写前后端数据交互的 schemas
4. 在 `lifeprism/server/services/` 创建单例 service，采用懒加载 (`lifeprism/utils/lazy_singleton.py`)

### 设计原则

- 所有实体使用 `id` 作为唯一标识（名称易变，不适合做标识）
- 若前后端字段冲突，以后端为准，修改前端
- 后端多余字段可删除，前端新增字段后端需补充

---

## 待定问题

- [ ]

