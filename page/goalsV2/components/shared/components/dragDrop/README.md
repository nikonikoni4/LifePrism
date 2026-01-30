# 跨区域拖拽组件库 (dragDrop)

基于 `@dnd-kit` 封装的通用跨区域拖拽解决方案，可独立迁移到任何 React 项目。

## 📦 目录结构

```
dragDrop/
├── index.ts                      # 统一导出
├── types.ts                      # 类型定义
├── context/
│   └── CrossAreaDndContext.tsx   # 跨区域拖拽上下文
├── components/
│   ├── DraggableItem.tsx         # 可拖拽项组件
│   └── DroppableArea.tsx         # 可放置区域组件
├── hooks/
│   └── useCrossAreaDnd.ts        # 拖拽状态管理 Hook
└── examples/
    └── TaskPoolCalendarExample.tsx  # 使用示例
```

## 🚀 快速开始

### 安装依赖

```bash
npm install @dnd-kit/core @dnd-kit/sortable @dnd-kit/utilities
```

### 方式一：使用 Provider 组件（推荐）

```tsx
import {
  CrossAreaDndProvider,
  DraggableItem,
  DroppableDateCell,
  DroppablePoolRoot,
} from '@/other_project/dragDrop';

function App() {
  const handleCrossAreaDrop = (dragItem, dropArea) => {
    if (dropArea.type === 'date-cell') {
      // 处理拖拽到日期格子
      scheduleTask(dragItem.payload, dropArea.payload.date);
    } else if (dropArea.type === 'pool-root') {
      // 处理拖拽回任务池
      unscheduleTask(dragItem.payload);
    }
  };

  return (
    <CrossAreaDndProvider
      onCrossAreaDrop={handleCrossAreaDrop}
      renderDragOverlay={(item) => <TaskPreview task={item.payload} />}
    >
      {/* 任务池 */}
      <DroppablePoolRoot>
        {tasks.map(task => (
          <DraggableItem
            key={task.id}
            id={task.id}
            type="task"
            source="task-pool"
            data={task}
          >
            <TaskCard task={task} />
          </DraggableItem>
        ))}
      </DroppablePoolRoot>

      {/* 日历 */}
      {dates.map(date => (
        <DroppableDateCell key={date} date={date}>
          <DateContent date={date} />
        </DroppableDateCell>
      ))}
    </CrossAreaDndProvider>
  );
}
```

### 方式二：使用 Hook（更灵活）

```tsx
import { useCrossAreaDnd } from '@/other_project/dragDrop';
import { DndContext, DragOverlay } from '@dnd-kit/core';

function App() {
  const {
    handleDragStart,
    handleDragEnd,
    handleDragOver,
    activeItem,
  } = useCrossAreaDnd({
    onCrossAreaDrop: (dragItem, dropArea) => {
      // 处理跨区域拖拽
    },
  });

  return (
    <DndContext
      onDragStart={handleDragStart}
      onDragOver={handleDragOver}
      onDragEnd={handleDragEnd}
    >
      {/* 你的内容 */}
      
      <DragOverlay>
        {activeItem && <TaskPreview task={activeItem.payload} />}
      </DragOverlay>
    </DndContext>
  );
}
```

## 📚 API 文档

### `CrossAreaDndProvider`

跨区域拖拽上下文提供者。

| Prop | Type | Description |
|------|------|-------------|
| `onCrossAreaDrop` | `(dragItem, dropArea, event) => void` | 跨区域拖拽完成回调 |
| `onDragStart` | `(event) => void` | 拖拽开始回调 |
| `onDragEnd` | `(event) => void` | 拖拽结束回调 |
| `renderDragOverlay` | `(dragItem) => ReactNode` | 拖拽预览渲染函数 |
| `enableKeyboard` | `boolean` | 是否启用键盘控制（默认 `true`） |
| `activationDistance` | `number` | 激活拖拽的距离（默认 `8`） |

### `DraggableItem`

可拖拽项包装组件。

| Prop | Type | Description |
|------|------|-------------|
| `id` | `string \| number` | 唯一标识 |
| `type` | `string` | 拖拽项类型（默认 `'item'`） |
| `source` | `DragSourceType` | 来源区域 |
| `data` | `T` | 携带的数据 |
| `disabled` | `boolean` | 是否禁用拖拽 |
| `draggingClassName` | `string` | 拖拽时的额外类名 |

### `DroppableArea`

通用可放置区域组件。

| Prop | Type | Description |
|------|------|-------------|
| `id` | `string \| number` | 唯一标识 |
| `type` | `DropTargetType` | 放置区域类型 |
| `data` | `T` | 携带的数据 |
| `accepts` | `string[]` | 接受的拖拽项类型 |
| `hoverClassName` | `string` | 悬停时的额外类名 |
| `hoverHint` | `string` | 悬停时显示的提示 |

### 预设放置区域组件

- `DroppableDateCell` - 日历日期格子
- `DroppableFolder` - 文件夹
- `DroppablePoolRoot` - 任务池根目录
- `DroppableTrash` - 删除区

### `useCrossAreaDnd` Hook

拖拽状态管理 Hook。

```tsx
const {
  dragState,           // 当前拖拽状态
  handleDragStart,     // DndContext 的 onDragStart
  handleDragOver,      // DndContext 的 onDragOver
  handleDragEnd,       // DndContext 的 onDragEnd
  isDragging,          // 是否正在拖拽
  activeItem,          // 当前拖拽的项
  overArea,            // 当前悬停的放置区域
  resetDragState,      // 重置状态
} = useCrossAreaDnd(options);
```

## 🎯 典型场景

### 任务池 → 日历

```tsx
<DroppablePoolRoot>
  {poolTasks.map(task => (
    <DraggableItem 
      id={task.id} 
      type="task" 
      source="task-pool" 
      data={task}
    >
      <TaskCard task={task} />
    </DraggableItem>
  ))}
</DroppablePoolRoot>

{dates.map(date => (
  <DroppableDateCell date={date}>
    {/* 日期内已安排的任务 */}
  </DroppableDateCell>
))}
```

### 文件夹分组

```tsx
{folders.map(folder => (
  <DroppableFolder folderId={folder.id} folderName={folder.name}>
    {folder.tasks.map(task => (
      <DraggableItem id={task.id} source="folder" data={task}>
        <TaskCard task={task} />
      </DraggableItem>
    ))}
  </DroppableFolder>
))}
```

## 🔄 与 todoItem 组件库配合

```tsx
import { TodoItem, TodoItemTree } from '@/other_project/todoItem';
import { 
  CrossAreaDndProvider, 
  DraggableItem 
} from '@/other_project/dragDrop';

// 包装 TodoItem
<DraggableItem id={task.id} type="task" source="pool" data={task}>
  <TodoItem todo={task} onUpdate={...} onDelete={...} />
</DraggableItem>
```

## 📋 迁移清单

将此组件库迁移到新项目时：

1. ✅ 复制整个 `dragDrop` 目录
2. ✅ 安装依赖：`@dnd-kit/core`, `@dnd-kit/sortable`, `@dnd-kit/utilities`
3. ✅ 更新导入路径
4. ✅ 根据需要自定义样式类名
