/**
 * 通用可放置区域组件
 * 
 * 提供：
 * - 放置目标注册
 * - 悬停状态样式
 * - 类型过滤
 */

import React from 'react';
import { useDroppable } from '@dnd-kit/core';
import type { DroppableAreaProps, DropTargetType } from '../types';

// =============================================================================
// Component
// =============================================================================

/**
 * 可放置区域包装组件
 * 
 * @example
 * ```tsx
 * <DroppableArea
 *   id={`date-${date}`}
 *   type="date-cell"
 *   data={{ date }}
 *   accepts={['task']}
 *   hoverClassName="bg-violet-100 border-violet-400"
 *   hoverHint="放置以安排到此日期"
 * >
 *   <DateContent date={date} />
 * </DroppableArea>
 * ```
 */
export function DroppableArea<T>({
    id,
    type,
    data,
    accepts,
    disabled = false,
    children,
    className = '',
    hoverClassName = 'bg-blue-50 border-blue-300',
    hoverHint,
}: DroppableAreaProps<T>) {
    const { setNodeRef, isOver, active } = useDroppable({
        id: String(id),
        disabled,
        data: {
            type,
            payload: data,
            accepts,
        },
    });

    // 检查当前拖拽项是否被接受
    const activeType = active?.data.current?.type;
    const isAccepted = !accepts || (activeType && accepts.includes(activeType));
    const shouldHighlight = isOver && isAccepted;

    return (
        <div
            ref={setNodeRef}
            className={`
                transition-all duration-200
                ${className}
                ${shouldHighlight ? hoverClassName : ''}
            `}
        >
            {children}

            {/* 悬停提示 */}
            {shouldHighlight && hoverHint && (
                <div className="flex items-center justify-center py-2 text-xs font-medium text-blue-600 animate-pulse">
                    {hoverHint}
                </div>
            )}
        </div>
    );
}

// =============================================================================
// 预设样式变体
// =============================================================================

/**
 * 日历日期格子放置区域
 */
export function DroppableDateCell({
    date,
    children,
    className = '',
    ...props
}: {
    date: string;
    children: React.ReactNode;
    className?: string;
} & Partial<DroppableAreaProps<{ date: string }>>) {
    return (
        <DroppableArea
            id={`date-${date}`}
            type="date-cell"
            data={{ date }}
            accepts={['task']}
            hoverClassName="bg-violet-100 border-violet-400 ring-2 ring-violet-300 shadow-lg"
            hoverHint={`放置到 ${date}`}
            className={`min-h-[80px] flex flex-col ${className}`}
            {...props}
        >
            {children}
        </DroppableArea>
    );
}

/**
 * 文件夹放置区域
 */
export function DroppableFolder({
    folderId,
    folderName,
    children,
    className = '',
    ...props
}: {
    folderId: number;
    folderName: string;
    children: React.ReactNode;
    className?: string;
} & Partial<DroppableAreaProps<{ folderId: number; folderName: string }>>) {
    return (
        <DroppableArea
            id={`folder-${folderId}`}
            type="folder"
            data={{ folderId, folderName }}
            accepts={['task']}
            hoverClassName="bg-amber-100 border-amber-400 shadow-inner"
            hoverHint={`放入 ${folderName}`}
            className={`p-2 border-2 border-dashed border-transparent rounded-lg ${className}`}
            {...props}
        >
            {children}
        </DroppableArea>
    );
}

/**
 * 任务池根目录放置区域
 */
export function DroppablePoolRoot({
    children,
    className = '',
    ...props
}: {
    children: React.ReactNode;
    className?: string;
} & Partial<DroppableAreaProps>) {
    return (
        <DroppableArea
            id="pool-root"
            type="pool-root"
            accepts={['task']}
            hoverClassName="bg-emerald-50/80 ring-2 ring-emerald-400/50 ring-inset"
            hoverHint="放置到任务池"
            className={`h-full ${className}`}
            {...props}
        >
            {children}
        </DroppableArea>
    );
}

/**
 * 删除区放置区域
 */
export function DroppableTrash({
    children,
    className = '',
    ...props
}: {
    children: React.ReactNode;
    className?: string;
} & Partial<DroppableAreaProps>) {
    return (
        <DroppableArea
            id="trash"
            type="trash"
            hoverClassName="bg-red-100 border-red-400 ring-2 ring-red-300"
            hoverHint="松开以删除"
            className={`p-4 border-2 border-dashed border-slate-200 rounded-lg ${className}`}
            {...props}
        >
            {children}
        </DroppableArea>
    );
}

// =============================================================================
// Hook: useDroppableArea
// =============================================================================

/**
 * 用于创建放置区域的 Hook
 * 当需要更细粒度控制时使用
 */
export function useDroppableArea<T>(options: {
    id: string | number;
    type: DropTargetType;
    data?: T;
    accepts?: string[];
    disabled?: boolean;
}) {
    const { setNodeRef, isOver, active, over } = useDroppable({
        id: String(options.id),
        disabled: options.disabled,
        data: {
            type: options.type,
            payload: options.data,
            accepts: options.accepts,
        },
    });

    // 检查当前拖拽项是否被接受
    const activeType = active?.data.current?.type;
    const isAccepted = !options.accepts || (activeType && options.accepts.includes(activeType));

    return {
        // dnd-kit 原始返回
        setNodeRef,
        isOver,
        active,
        over,
        // 便捷属性
        isAccepted,
        shouldHighlight: isOver && isAccepted,
        activeItemData: active?.data.current,
    };
}

export default DroppableArea;
