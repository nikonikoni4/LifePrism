/**
 * 跨区域拖拽上下文组件
 * 
 * 封装 @dnd-kit/core 的 DndContext，提供：
 * - 统一的跨区域拖拽管理
 * - 拖拽状态追踪
 * - 自定义拖拽预览层
 * - 事件处理封装
 */

import React, { useState, useCallback, useMemo } from 'react';
import {
    DndContext,
    DragOverlay,
    pointerWithin,
    rectIntersection,
    KeyboardSensor,
    PointerSensor,
    useSensor,
    useSensors,
    DragStartEvent,
    DragEndEvent,
    DragOverEvent,
    CollisionDetection,
} from '@dnd-kit/core';
import { sortableKeyboardCoordinates } from '@dnd-kit/sortable';
import type {
    CrossAreaDndContextProps,
    DragItemData,
    DropAreaData,
    DragState,
} from '../types';

// =============================================================================
// Context
// =============================================================================

interface CrossAreaDndContextValue<T = unknown> {
    dragState: DragState<T>;
}

const CrossAreaDndStateContext = React.createContext<CrossAreaDndContextValue | null>(null);

/**
 * 获取跨区域拖拽状态的 Hook
 */
export function useCrossAreaDndState<T = unknown>(): CrossAreaDndContextValue<T> {
    const context = React.useContext(CrossAreaDndStateContext);
    if (!context) {
        throw new Error('useCrossAreaDndState must be used within CrossAreaDndProvider');
    }
    return context as CrossAreaDndContextValue<T>;
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

// =============================================================================
// Component
// =============================================================================

/**
 * 跨区域拖拽上下文提供者
 * 
 * @example
 * ```tsx
 * <CrossAreaDndProvider
 *   onCrossAreaDrop={(dragItem, dropArea) => {
 *     console.log('跨区域拖拽完成', dragItem, dropArea);
 *   }}
 *   renderDragOverlay={(dragItem) => (
 *     <TaskCard task={dragItem.payload} isOverlay />
 *   )}
 * >
 *   <TaskPool />
 *   <Calendar />
 * </CrossAreaDndProvider>
 * ```
 */
export function CrossAreaDndProvider<TDrag = unknown, TDrop = unknown>({
    children,
    onCrossAreaDrop,
    onDragStart,
    onDragEnd,
    onDragOver,
    renderDragOverlay,
    enableKeyboard = true,
    activationDistance = 8,
}: CrossAreaDndContextProps<TDrag, TDrop>) {
    // 拖拽状态
    const [dragState, setDragState] = useState<DragState<TDrag>>({
        isDragging: false,
        activeItem: null,
        overArea: null,
    });

    // 传感器配置
    const sensors = useSensors(
        useSensor(PointerSensor, {
            activationConstraint: {
                distance: activationDistance,
            },
        }),
        ...(enableKeyboard
            ? [
                useSensor(KeyboardSensor, {
                    coordinateGetter: sortableKeyboardCoordinates,
                }),
            ]
            : [])
    );

    // 碰撞检测策略：优先使用指针位置，其次使用矩形相交
    const collisionDetection: CollisionDetection = useCallback((args) => {
        const pointerCollisions = pointerWithin(args);
        if (pointerCollisions.length > 0) {
            return pointerCollisions;
        }
        return rectIntersection(args);
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

        if (onDragOver && dragState.activeItem) {
            onDragOver({
                active: event.active,
                over: event.over,
                dragItem: dragState.activeItem,
                dropArea,
            });
        }
    }, [onDragOver, dragState.activeItem]);

    // 拖拽结束处理
    const handleDragEnd = useCallback((event: DragEndEvent) => {
        const dragItem = extractDragItemData<TDrag>(event.active);
        const dropArea = extractDropAreaData<TDrop>(event.over);
        const isCrossArea = isCrossAreaDrop(dragItem, dropArea);

        // 重置状态
        setDragState({
            isDragging: false,
            activeItem: null,
            overArea: null,
        });

        // 构建事件数据
        const eventData = {
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

        // 如果是跨区域拖拽且有有效的放置目标，触发跨区域回调
        if (isCrossArea && dragItem && dropArea && onCrossAreaDrop) {
            // 检查是否接受该类型
            if (!dropArea.accepts || dropArea.accepts.includes(dragItem.type)) {
                onCrossAreaDrop(dragItem, dropArea, eventData);
            }
        }
    }, [onDragEnd, onCrossAreaDrop]);

    // Context 值
    const contextValue = useMemo(() => ({
        dragState,
    }), [dragState]);

    return (
        <CrossAreaDndStateContext.Provider value={contextValue}>
            <DndContext
                sensors={sensors}
                collisionDetection={collisionDetection}
                onDragStart={handleDragStart}
                onDragOver={handleDragOver}
                onDragEnd={handleDragEnd}
            >
                {children}

                {/* 拖拽预览层 */}
                <DragOverlay dropAnimation={null}>
                    {dragState.isDragging && dragState.activeItem && renderDragOverlay && (
                        renderDragOverlay(dragState.activeItem)
                    )}
                </DragOverlay>
            </DndContext>
        </CrossAreaDndStateContext.Provider>
    );
}

export default CrossAreaDndProvider;
