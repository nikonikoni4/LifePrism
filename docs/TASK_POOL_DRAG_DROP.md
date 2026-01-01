# 任务池文件夹系统 - 拖拽交互实现文档

## 概述

任务池（Task Pool）采用类似 IDE 文件资源管理器的树形结构，支持一级文件夹管理和拖拽交互。本文档说明当前的交互逻辑和实现细节。

## 文件结构

```
frontend/page/goals/
├── components/
│   ├── PlanTabView.tsx      # 主视图，包含 DnD 上下文和状态管理
│   ├── TaskPoolTree.tsx     # 任务池树形组件，包含文件夹和 todo 渲染
│   └── TaskDetailPanel.tsx  # 任务详情面板
└── types.ts                 # 类型定义（TaskFolder, TaskPoolTreeData）
```

## 数据结构

### TaskFolder
```typescript
interface TaskFolder {
    id: string;           // 文件夹唯一标识
    name: string;         // 文件夹名称
    isExpanded: boolean;  // 是否展开
    todoIds: number[];    // 文件夹内的 todo ID 列表
}
```

### 状态管理
- `taskFolders: TaskFolder[]` - 文件夹列表（临时状态，不持久化）
- `rootTodoIds: number[]` - 根目录的 todo ID 列表
- `taskPoolItems: TodoItem[]` - 所有任务池中的 todo

## 拖拽交互逻辑

### 1. 拖拽优先级

| 场景 | 判定逻辑 | 行为 |
|------|---------|------|
| **同容器内拖拽** | `sourceFolderId === effectiveTargetFolderId` | 内部排序 |
| **跨容器拖拽** | `sourceFolderId !== effectiveTargetFolderId` | 仅判定文件夹归属，不排序 |

### 2. Drop 目标类型

| Drop Target ID 格式 | 说明 |
|---------------------|------|
| `folder-header-{folderId}` | 文件夹头部（优先级最高） |
| `folder-{folderId}` | 文件夹内容区域 |
| `pool-root` | 根目录区域 |
| `task-pool` | 任务池整体（兼容旧逻辑） |
| `day-{date}` | 周视图的日期区域 |

### 3. 交互规则

#### 外部 → 文件夹内
- 只判定文件夹归属
- 忽略落在文件夹内 todo 上的排序判定
- 自动添加到文件夹末尾

#### 文件夹内 → 文件夹内
- 判定内部排序
- 支持拖拽重排

#### 文件夹 ↔ 根目录
- 从文件夹拖出到根目录
- 从根目录拖入文件夹

#### 任务池 ↔ 周视图
- 任务池 → 日期：激活任务，设置日期
- 日期 → 任务池：停用任务，清除日期

## 实现细节

### 1. Droppable 组件

```tsx
// 文件夹头部 - 始终可见的 drop 目标
const DroppableFolderHeader: React.FC<Props> = ({ folderId, children }) => {
    const { setNodeRef, isOver } = useDroppable({
        id: `folder-header-${folderId}`,
        data: { type: 'folder', folderId }
    });
    // isOver 时显示视觉反馈
};

// 文件夹内容区域
const DroppableFolder: React.FC<Props> = ({ folderId, children }) => {
    const { setNodeRef, isOver } = useDroppable({
        id: `folder-${folderId}`,
        data: { type: 'folder', folderId }
    });
};

// 根目录区域
const DroppableRoot: React.FC<Props> = ({ children }) => {
    const { setNodeRef, isOver } = useDroppable({
        id: 'pool-root',
        data: { type: 'pool-root' }
    });
};
```

### 2. Sortable 组件

```tsx
const SortablePoolTreeItem: React.FC<Props> = ({ task, folderId }) => {
    const { ... } = useSortable({
        id: task.id,
        data: { 
            type: 'pool-item', 
            task, 
            source: 'pool',
            folderId  // 记录来源文件夹
        }
    });
};
```

### 3. handleDragEnd 核心逻辑

```typescript
const handleDragEnd = async (event: DragEndEvent) => {
    const { active, over, delta } = event;
    
    // 1. 确定来源
    const sourceFolderId = active.data.current?.folderId ?? null;
    
    // 2. 确定目标
    const isToFolderHeader = overId.startsWith('folder-header-');
    const isToFolderContent = overId.startsWith('folder-') && !isToFolderHeader;
    const targetFolderId = isToFolderHeader 
        ? overId.replace('folder-header-', '')
        : (isToFolderContent ? overId.replace('folder-', '') : null);
    
    // 3. 判定是否同容器
    const isSameContainer = sourceFolderId === effectiveTargetFolderId;
    
    if (isSameContainer && isOverPoolItem) {
        // 内部排序
    } else if (needsMove) {
        // 跨容器移动
    }
};
```

## 视觉反馈

| 状态 | 样式 |
|------|------|
| 文件夹头部悬停 | `bg-blue-100 ring-2 ring-blue-400 shadow-md` + "放入" 徽章 |
| 文件夹内容区域悬停 | `bg-blue-100 border-blue-400 border-dashed` + "放置到此文件夹" 提示 |
| 根目录区域悬停 | `bg-emerald-100 border-emerald-400` + "放置到根目录" 提示 |
| 拖拽中的项目 | `opacity-50 shadow-lg ring-2 ring-blue-300` |

## 注意事项

1. **临时状态**: 文件夹结构目前不持久化，刷新页面会丢失
2. **Goal 关联**: 创建任务时会关联当前选中的 Goal
3. **API 调用**: 跨容器移动会调用 `todoApi.updateTodo` 更新状态和日期

## 未来改进

- [ ] 文件夹结构持久化到后端
- [ ] 支持文件夹拖拽排序
