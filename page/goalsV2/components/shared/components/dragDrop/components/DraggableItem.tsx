/**
 * 通用可拖拽项组件
 * 
 * 提供：
 * - 拖拽手柄或整体拖拽
 * - 拖拽状态样式
 * - 自定义数据携带
 */

import React, { forwardRef } from 'react';
import { useDraggable } from '@dnd-kit/core';
import { CSS } from '@dnd-kit/utilities';
import type { DraggableItemProps, DragSourceType } from '../types';

// =============================================================================
// Component
// =============================================================================

/**
 * 可拖拽项包装组件
 * 
 * @example
 * ```tsx
 * <DraggableItem
 *   id={task.id}
 *   type="task"
 *   source="task-pool"
 *   data={task}
 *   draggingClassName="opacity-50 shadow-xl"
 * >
 *   <TaskCard task={task} />
 * </DraggableItem>
 * ```
 */
function DraggableItemInner<T>(
    {
        id,
        type = 'item',
        source = 'list' as DragSourceType,
        data,
        parentId,
        withChildren = false,
        disabled = false,
        children,
        className = '',
        draggingClassName = 'opacity-60 shadow-lg',
    }: DraggableItemProps<T>,
    ref: React.ForwardedRef<HTMLDivElement>
) {
    const {
        attributes,
        listeners,
        setNodeRef,
        transform,
        isDragging,
    } = useDraggable({
        id,
        disabled,
        data: {
            type,
            source,
            payload: data,
            parentId,
            withChildren,
        },
    });

    // 当使用 DragOverlay 时，原始元素不应该移动
    // 只有 DragOverlay 负责显示跟随鼠标的预览
    // 拖拽时原始元素保持原位，仅通过 draggingClassName 改变样式
    const style: React.CSSProperties = {};

    // 合并 ref
    const mergedRef = React.useCallback(
        (node: HTMLDivElement | null) => {
            setNodeRef(node);
            if (typeof ref === 'function') {
                ref(node);
            } else if (ref) {
                (ref as React.MutableRefObject<HTMLDivElement | null>).current = node;
            }
        },
        [setNodeRef, ref]
    );

    return (
        <div
            ref={mergedRef}
            style={style}
            className={`${className} ${isDragging ? draggingClassName : ''}`}
            {...attributes}
            {...listeners}
        >
            {children}
        </div>
    );
}

// 使用 forwardRef 并保持泛型
export const DraggableItem = forwardRef(DraggableItemInner) as <T>(
    props: DraggableItemProps<T> & { ref?: React.Ref<HTMLDivElement> }
) => React.ReactElement;

// =============================================================================
// 拖拽手柄组件
// =============================================================================

interface DragHandleProps {
    className?: string;
    children?: React.ReactNode;
}

/**
 * 拖拽手柄组件
 * 用于只允许通过特定区域拖拽的场景
 * 
 * 注意：需要配合 useSortable 的 listeners 使用
 * 
 * @example
 * ```tsx
 * const { listeners, attributes } = useSortable({ id });
 * 
 * <div>
 *   <DragHandle {...listeners} {...attributes}>
 *     <GripVertical />
 *   </DragHandle>
 *   <span>Content</span>
 * </div>
 * ```
 */
export const DragHandle: React.FC<DragHandleProps & React.HTMLAttributes<HTMLDivElement>> = ({
    className = '',
    children,
    ...props
}) => {
    return (
        <div
            className={`cursor-grab active:cursor-grabbing ${className}`}
            {...props}
        >
            {children}
        </div>
    );
};

// =============================================================================
// Hook: useDraggableData
// =============================================================================

/**
 * 用于构建拖拽数据的 Hook
 * 当需要更细粒度控制时使用
 */
export function useDraggableData<T>(options: {
    id: string | number;
    type: string;
    source: DragSourceType;
    data: T;
    parentId?: string | number | null;
    withChildren?: boolean;
    disabled?: boolean;
}) {
    const {
        attributes,
        listeners,
        setNodeRef,
        transform,
        isDragging,
        over,
        active,
    } = useDraggable({
        id: options.id,
        disabled: options.disabled,
        data: {
            type: options.type,
            source: options.source,
            payload: options.data,
            parentId: options.parentId,
            withChildren: options.withChildren,
        },
    });

    const style: React.CSSProperties = {
        transform: CSS.Translate.toString(transform),
    };

    return {
        // dnd-kit 原始返回
        attributes,
        listeners,
        setNodeRef,
        isDragging,
        over,
        active,
        // 预处理的样式
        style,
        // 便捷方法
        isOver: over?.id === options.id,
    };
}

export default DraggableItem;
