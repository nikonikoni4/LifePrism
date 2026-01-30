/**
 * 跨区域拖拽组件库 - 类型定义
 * 
 * 这是一个通用的拖拽类型系统，支持：
 * - 自定义拖拽项数据
 * - 自定义放置区域标识
 * - 跨区域拖拽事件处理
 */

import type { Active, Over } from '@dnd-kit/core';

// =============================================================================
// 基础类型
// =============================================================================

/**
 * 拖拽项的来源区域类型
 * 可根据需要扩展
 */
export type DragSourceType =
    | 'task-pool'      // 任务池
    | 'calendar'       // 日历
    | 'tree'           // 树形结构
    | 'list'           // 列表
    | string;          // 自定义

/**
 * 放置目标的类型
 */
export type DropTargetType =
    | 'date-cell'      // 日历日期格子
    | 'folder'         // 文件夹
    | 'pool-root'      // 任务池根目录
    | 'tree-node'      // 树节点
    | 'trash'          // 删除区
    | string;          // 自定义

// =============================================================================
// 拖拽数据结构
// =============================================================================

/**
 * 可拖拽项携带的数据
 * 通过泛型 T 支持自定义数据类型
 */
export interface DragItemData<T = unknown> {
    /** 拖拽项的唯一标识 */
    id: string | number;
    /** 拖拽项类型标识 */
    type: string;
    /** 来源区域 */
    source: DragSourceType;
    /** 附加数据（如完整的任务对象） */
    payload: T;
    /** 父节点 ID（用于树形结构） */
    parentId?: string | number | null;
    /** 是否携带子节点 */
    withChildren?: boolean;
}

/**
 * 放置区域携带的数据
 */
export interface DropAreaData<T = unknown> {
    /** 放置区域的唯一标识 */
    id: string | number;
    /** 放置区域类型 */
    type: DropTargetType;
    /** 附加数据（如日期、文件夹信息等） */
    payload?: T;
    /** 是否接受特定类型的拖拽项 */
    accepts?: string[];
}

// =============================================================================
// 事件类型
// =============================================================================

/**
 * 拖拽开始事件数据
 */
export interface DragStartEventData<T = unknown> {
    active: Active;
    dragItem: DragItemData<T>;
}

/**
 * 拖拽结束事件数据
 */
export interface DragEndEventData<TDrag = unknown, TDrop = unknown> {
    active: Active;
    over: Over | null;
    dragItem: DragItemData<TDrag>;
    dropArea: DropAreaData<TDrop> | null;
    /** 是否是跨区域拖拽 */
    isCrossArea: boolean;
}

/**
 * 拖拽悬停事件数据
 */
export interface DragOverEventData<TDrag = unknown, TDrop = unknown> {
    active: Active;
    over: Over | null;
    dragItem: DragItemData<TDrag>;
    dropArea: DropAreaData<TDrop> | null;
}

// =============================================================================
// 回调函数类型
// =============================================================================

/**
 * 跨区域拖拽完成的回调
 */
export type OnCrossAreaDrop<TDrag = unknown, TDrop = unknown> = (
    dragItem: DragItemData<TDrag>,
    dropArea: DropAreaData<TDrop>,
    event: DragEndEventData<TDrag, TDrop>
) => void | Promise<void>;

/**
 * 同区域内排序的回调
 */
export type OnSameAreaReorder<T = unknown> = (
    items: T[],
    activeIndex: number,
    overIndex: number
) => void | Promise<void>;

/**
 * 拖拽状态变化回调
 */
export type OnDragStateChange<T = unknown> = (
    isDragging: boolean,
    dragItem: DragItemData<T> | null
) => void;

// =============================================================================
// 组件 Props 类型
// =============================================================================

/**
 * 可拖拽项组件的 Props
 */
export interface DraggableItemProps<T = unknown> {
    /** 唯一标识 */
    id: string | number;
    /** 拖拽项类型 */
    type?: string;
    /** 来源区域 */
    source?: DragSourceType;
    /** 携带的数据 */
    data: T;
    /** 父节点 ID */
    parentId?: string | number | null;
    /** 是否携带子节点 */
    withChildren?: boolean;
    /** 是否禁用拖拽 */
    disabled?: boolean;
    /** 子元素 */
    children: React.ReactNode;
    /** 自定义类名 */
    className?: string;
    /** 拖拽时的额外类名 */
    draggingClassName?: string;
}

/**
 * 可放置区域组件的 Props
 */
export interface DroppableAreaProps<T = unknown> {
    /** 唯一标识 */
    id: string | number;
    /** 放置区域类型 */
    type: DropTargetType;
    /** 携带的数据 */
    data?: T;
    /** 接受的拖拽项类型 */
    accepts?: string[];
    /** 是否禁用放置 */
    disabled?: boolean;
    /** 子元素 */
    children: React.ReactNode;
    /** 自定义类名 */
    className?: string;
    /** 悬停时的额外类名 */
    hoverClassName?: string;
    /** 悬停时显示的提示 */
    hoverHint?: string;
}

/**
 * 跨区域拖拽上下文的 Props
 */
export interface CrossAreaDndContextProps<TDrag = unknown, TDrop = unknown> {
    /** 子元素 */
    children: React.ReactNode;
    /** 跨区域拖拽完成回调 */
    onCrossAreaDrop?: OnCrossAreaDrop<TDrag, TDrop>;
    /** 拖拽开始回调 */
    onDragStart?: (event: DragStartEventData<TDrag>) => void;
    /** 拖拽结束回调（不论是否跨区域） */
    onDragEnd?: (event: DragEndEventData<TDrag, TDrop>) => void;
    /** 拖拽悬停回调 */
    onDragOver?: (event: DragOverEventData<TDrag, TDrop>) => void;
    /** 拖拽预览渲染函数 */
    renderDragOverlay?: (dragItem: DragItemData<TDrag>) => React.ReactNode;
    /** 是否启用键盘传感器 */
    enableKeyboard?: boolean;
    /** 指针传感器激活距离（像素） */
    activationDistance?: number;
}

// =============================================================================
// 状态类型
// =============================================================================

/**
 * 拖拽状态
 */
export interface DragState<T = unknown> {
    /** 是否正在拖拽 */
    isDragging: boolean;
    /** 当前拖拽的项 */
    activeItem: DragItemData<T> | null;
    /** 当前悬停的放置区域 */
    overArea: DropAreaData | null;
}
