/**
 * 跨区域拖拽状态管理 Hook
 * 
 * 提供统一的拖拽状态管理和事件处理
 */

import { useState, useCallback, useMemo } from 'react';
import { DragStartEvent, DragEndEvent, DragOverEvent } from '@dnd-kit/core';
import type {
    DragItemData,
    DropAreaData,
    DragState,
    OnCrossAreaDrop,
    DragStartEventData,
    DragEndEventData,
    DragOverEventData,
} from '../types';

// =============================================================================
// Types
// =============================================================================

interface UseCrossAreaDndOptions<TDrag = unknown, TDrop = unknown> {
    /** 跨区域拖拽完成回调 */
    onCrossAreaDrop?: OnCrossAreaDrop<TDrag, TDrop>;
    /** 拖拽开始回调 */
    onDragStart?: (event: DragStartEventData<TDrag>) => void;
    /** 拖拽结束回调 */
    onDragEnd?: (event: DragEndEventData<TDrag, TDrop>) => void;
    /** 拖拽悬停回调 */
    onDragOver?: (event: DragOverEventData<TDrag, TDrop>) => void;
}

interface UseCrossAreaDndReturn<TDrag = unknown, TDrop = unknown> {
    /** 当前拖拽状态 */
    dragState: DragState<TDrag>;
    /** DndContext 的 onDragStart 处理函数 */
    handleDragStart: (event: DragStartEvent) => void;
    /** DndContext 的 onDragOver 处理函数 */
    handleDragOver: (event: DragOverEvent) => void;
    /** DndContext 的 onDragEnd 处理函数 */
    handleDragEnd: (event: DragEndEvent) => void;
    /** 是否正在拖拽 */
    isDragging: boolean;
    /** 当前拖拽的项 */
    activeItem: DragItemData<TDrag> | null;
    /** 当前悬停的放置区域 */
    overArea: DropAreaData<TDrop> | null;
    /** 重置拖拽状态 */
    resetDragState: () => void;
}

// =============================================================================
// Helper Functions
// =============================================================================

/**
 * 从 dnd-kit 事件中提取拖拽项数据
 */
function extractDragItemData<T>(active: DragStartEvent['active']): DragItemData<T> | null {
    const data = active.data.current;
    if (!data) return null;

    return {
        id: active.id,
        type: data.type || 'unknown',
        source: data.source || 'unknown',
        payload: data.payload as T,
        parentId: data.parentId,
        withChildren: data.withChildren,
    };
}

/**
 * 从 dnd-kit 事件中提取放置区域数据
 */
function extractDropAreaData<T>(over: DragEndEvent['over']): DropAreaData<T> | null {
    if (!over) return null;

    const data = over.data.current;
    if (!data) return null;

    return {
        id: over.id,
        type: data.type || 'unknown',
        payload: data.payload as T,
        accepts: data.accepts,
    };
}

/**
 * 判断是否是跨区域拖拽
 */
function isCrossAreaDrop(
    dragItem: DragItemData | null,
    dropArea: DropAreaData | null
): boolean {
    if (!dragItem || !dropArea) return false;
    return dragItem.source !== dropArea.type;
}

/**
 * 检查放置区域是否接受该拖拽项类型
 */
function isAcceptedDrop(
    dragItem: DragItemData | null,
    dropArea: DropAreaData | null
): boolean {
    if (!dragItem || !dropArea) return false;
    if (!dropArea.accepts) return true;
    return dropArea.accepts.includes(dragItem.type);
}

// =============================================================================
// Hook
// =============================================================================

/**
 * 跨区域拖拽状态管理 Hook
 * 
 * @example
 * ```tsx
 * const {
 *   dragState,
 *   handleDragStart,
 *   handleDragEnd,
 *   handleDragOver,
 *   activeItem,
 * } = useCrossAreaDnd({
 *   onCrossAreaDrop: (dragItem, dropArea) => {
 *     if (dropArea.type === 'date-cell') {
 *       scheduleTask(dragItem.payload, dropArea.payload.date);
 *     }
 *   },
 * });
 * 
 * return (
 *   <DndContext
 *     onDragStart={handleDragStart}
 *     onDragOver={handleDragOver}
 *     onDragEnd={handleDragEnd}
 *   >
 *     {children}
 *     <DragOverlay>
 *       {activeItem && <TaskPreview task={activeItem.payload} />}
 *     </DragOverlay>
 *   </DndContext>
 * );
 * ```
 */
export function useCrossAreaDnd<TDrag = unknown, TDrop = unknown>(
    options: UseCrossAreaDndOptions<TDrag, TDrop> = {}
): UseCrossAreaDndReturn<TDrag, TDrop> {
    const { onCrossAreaDrop, onDragStart, onDragEnd, onDragOver } = options;

    // 拖拽状态
    const [dragState, setDragState] = useState<DragState<TDrag>>({
        isDragging: false,
        activeItem: null,
        overArea: null,
    });

    // 重置状态
    const resetDragState = useCallback(() => {
        setDragState({
            isDragging: false,
            activeItem: null,
            overArea: null,
        });
    }, []);

    // 拖拽开始处理
    const handleDragStart = useCallback((event: DragStartEvent) => {
        const dragItem = extractDragItemData<TDrag>(event.active);

        setDragState({
            isDragging: true,
            activeItem: dragItem,
            overArea: null,
        });

        if (dragItem && onDragStart) {
            onDragStart({
                active: event.active,
                dragItem,
            });
        }
    }, [onDragStart]);

    // 拖拽悬停处理
    const handleDragOver = useCallback((event: DragOverEvent) => {
        const dropArea = extractDropAreaData<TDrop>(event.over);

        setDragState(prev => ({
            ...prev,
            overArea: dropArea,
        }));

        if (onDragOver) {
            const dragItem = extractDragItemData<TDrag>(event.active);
            if (dragItem) {
                onDragOver({
                    active: event.active,
                    over: event.over,
                    dragItem,
                    dropArea,
                });
            }
        }
    }, [onDragOver]);

    // 拖拽结束处理
    const handleDragEnd = useCallback((event: DragEndEvent) => {
        const dragItem = extractDragItemData<TDrag>(event.active);
        const dropArea = extractDropAreaData<TDrop>(event.over);
        const isCrossArea = isCrossAreaDrop(dragItem, dropArea);
        const isAccepted = isAcceptedDrop(dragItem, dropArea);

        // 重置状态
        resetDragState();

        // 构建事件数据
        const eventData: DragEndEventData<TDrag, TDrop> = {
            active: event.active,
            over: event.over,
            dragItem: dragItem!,
            dropArea,
            isCrossArea,
        };

        // 触发通用回调
        if (onDragEnd) {
            onDragEnd(eventData);
        }

        // 如果是跨区域拖拽且被接受，触发跨区域回调
        if (isCrossArea && isAccepted && dragItem && dropArea && onCrossAreaDrop) {
            onCrossAreaDrop(dragItem, dropArea, eventData);
        }
    }, [onDragEnd, onCrossAreaDrop, resetDragState]);

    // 便捷属性
    const result = useMemo(() => ({
        dragState,
        handleDragStart,
        handleDragOver,
        handleDragEnd,
        isDragging: dragState.isDragging,
        activeItem: dragState.activeItem,
        overArea: dragState.overArea as DropAreaData<TDrop> | null,
        resetDragState,
    }), [dragState, handleDragStart, handleDragOver, handleDragEnd, resetDragState]);

    return result;
}

export default useCrossAreaDnd;
