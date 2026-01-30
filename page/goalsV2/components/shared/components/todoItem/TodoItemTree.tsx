import React, { useState, useCallback } from 'react';
import { ChevronRight, ChevronDown } from 'lucide-react';
import {
    DndContext,
    closestCenter,
    KeyboardSensor,
    PointerSensor,
    useSensor,
    useSensors,
    DragEndEvent,
} from '@dnd-kit/core';
import {
    SortableContext,
    sortableKeyboardCoordinates,
    verticalListSortingStrategy,
} from '@dnd-kit/sortable';
import { TodoItem as TodoItemType } from './types';
import { TodoItem } from './TodoItem';

// ============================================================================
// Types
// ============================================================================

interface TodoItemTreeProps {
    /** 树形结构的 TodoItem 数组（已构建好 children） */
    items: TodoItemType[];
    /** 当前层级（内部递归使用，外部调用时无需传入） */
    level?: number;
    /** 最大缩进层级（超过此层级不再增加缩进） */
    maxIndentLevel?: number;
    /** 是否支持折叠 */
    collapsible?: boolean;
    /** 初始展开的节点 ID 集合 */
    defaultExpandedIds?: Set<number>;
    /** 是否启用拖拽排序 */
    sortable?: boolean;
    /** 选中的任务 ID */
    selectedId?: number | null;
    /** 更新任务回调 */
    onUpdate: (id: number, updates: Partial<TodoItemType>) => void;
    /** 删除任务回调 */
    onDelete: (id: number) => void;
    /** 选择任务回调 */
    onSelect?: (id: number) => void;
    /** 拖拽结束回调 */
    onDragEnd?: (event: DragEndEvent) => void;
    /** 展开/折叠变化回调 */
    onExpandChange?: (id: number, expanded: boolean) => void;
    /** 是否显示来源标签 */
    showSource?: boolean;
    /** 是否显示日期标签 */
    showDate?: boolean;
}

interface TodoItemNodeProps {
    item: TodoItemType;
    level: number;
    maxIndentLevel: number;
    collapsible: boolean;
    isExpanded: boolean;
    selectedId?: number | null;
    onToggleExpand: (id: number) => void;
    onUpdate: (id: number, updates: Partial<TodoItemType>) => void;
    onDelete: (id: number) => void;
    onSelect?: (id: number) => void;
    showSource?: boolean;
    showDate?: boolean;
    renderChildren: () => React.ReactNode;
}

// ============================================================================
// Constants
// ============================================================================

const INDENT_PX = 28; // 每层缩进像素

// ============================================================================
// Sub Components
// ============================================================================

/**
 * 单个树节点（包含展开/折叠按钮和子节点渲染）
 */
const TodoItemNode: React.FC<TodoItemNodeProps> = ({
    item,
    level,
    maxIndentLevel,
    collapsible,
    isExpanded,
    selectedId,
    onToggleExpand,
    onUpdate,
    onDelete,
    onSelect,
    showSource,
    showDate,
    renderChildren,
}) => {
    const hasChildren = item.children && item.children.length > 0;
    const indent = Math.min(level, maxIndentLevel) * INDENT_PX;

    return (
        <div className="relative">
            {/* 连接线（可选，增加视觉层级感） */}
            {level > 0 && (
                <div
                    className="absolute top-0 bottom-0 border-l-2 border-slate-200/60"
                    style={{ left: indent - INDENT_PX / 2 - 1 }}
                />
            )}

            <div
                className="flex items-start gap-1"
                style={{ paddingLeft: indent }}
            >
                {/* 展开/折叠按钮 */}
                {collapsible && hasChildren ? (
                    <button
                        onClick={(e) => {
                            e.stopPropagation();
                            onToggleExpand(item.id);
                        }}
                        className="mt-3 p-0.5 rounded hover:bg-slate-100 text-slate-400 hover:text-slate-600 transition-colors flex-shrink-0"
                    >
                        {isExpanded ? (
                            <ChevronDown size={16} />
                        ) : (
                            <ChevronRight size={16} />
                        )}
                    </button>
                ) : (
                    // 占位符，保持对齐
                    <div className="w-5 flex-shrink-0" />
                )}

                {/* TodoItem 组件 */}
                <div className="flex-1 min-w-0">
                    <TodoItem
                        todo={item}
                        isActive={selectedId === item.id}
                        onUpdate={onUpdate}
                        onDelete={onDelete}
                        onSelect={onSelect}
                        showSource={showSource}
                        showDate={showDate}
                    />
                </div>
            </div>

            {/* 子节点 */}
            {hasChildren && isExpanded && (
                <div className="relative">
                    {renderChildren()}
                </div>
            )}
        </div>
    );
};

// ============================================================================
// Main Component
// ============================================================================

/**
 * TodoItemTree - 递归渲染层级结构的容器组件
 *
 * 支持：
 * - 无限层级嵌套
 * - 展开/折叠
 * - 可选的拖拽排序
 * - 连接线视觉效果
 */
export const TodoItemTree: React.FC<TodoItemTreeProps> = ({
    items,
    level = 0,
    maxIndentLevel = 5,
    collapsible = true,
    defaultExpandedIds,
    sortable = false,
    selectedId,
    onUpdate,
    onDelete,
    onSelect,
    onDragEnd,
    onExpandChange,
    showSource = true,
    showDate = true,
}) => {
    // 展开状态管理
    const [expandedIds, setExpandedIds] = useState<Set<number>>(() => {
        return defaultExpandedIds || new Set();
    });

    const toggleExpand = useCallback((id: number) => {
        setExpandedIds(prev => {
            const next = new Set(prev);
            const willExpand = !next.has(id);
            if (willExpand) {
                next.add(id);
            } else {
                next.delete(id);
            }
            onExpandChange?.(id, willExpand);
            return next;
        });
    }, [onExpandChange]);

    // 拖拽传感器配置
    const sensors = useSensors(
        useSensor(PointerSensor, {
            activationConstraint: {
                distance: 8,
            },
        }),
        useSensor(KeyboardSensor, {
            coordinateGetter: sortableKeyboardCoordinates,
        })
    );

    // 递归渲染子节点
    const renderItems = (itemList: TodoItemType[], currentLevel: number) => {
        return itemList.map(item => (
            <TodoItemNode
                key={item.id}
                item={item}
                level={currentLevel}
                maxIndentLevel={maxIndentLevel}
                collapsible={collapsible}
                isExpanded={expandedIds.has(item.id)}
                selectedId={selectedId}
                onToggleExpand={toggleExpand}
                onUpdate={onUpdate}
                onDelete={onDelete}
                onSelect={onSelect}
                showSource={showSource}
                showDate={showDate}
                renderChildren={() =>
                    item.children && item.children.length > 0
                        ? renderItems(item.children, currentLevel + 1)
                        : null
                }
            />
        ));
    };

    // 如果启用排序，包裹 DndContext
    if (sortable && level === 0) {
        const allIds = items.map(item => item.id);

        return (
            <DndContext
                sensors={sensors}
                collisionDetection={closestCenter}
                onDragEnd={onDragEnd}
            >
                <SortableContext
                    items={allIds}
                    strategy={verticalListSortingStrategy}
                >
                    <div className="space-y-0">
                        {renderItems(items, level)}
                    </div>
                </SortableContext>
            </DndContext>
        );
    }

    return (
        <div className="space-y-0">
            {renderItems(items, level)}
        </div>
    );
};

// ============================================================================
// Utility Hooks
// ============================================================================

/**
 * 用于管理展开状态的 Hook
 * 可在页面级使用，提供更细粒度的控制
 */
export function useExpandedState(initialIds: number[] = []) {
    const [expandedIds, setExpandedIds] = useState<Set<number>>(
        () => new Set(initialIds)
    );

    const expand = useCallback((id: number) => {
        setExpandedIds(prev => new Set([...prev, id]));
    }, []);

    const collapse = useCallback((id: number) => {
        setExpandedIds(prev => {
            const next = new Set(prev);
            next.delete(id);
            return next;
        });
    }, []);

    const toggle = useCallback((id: number) => {
        setExpandedIds(prev => {
            const next = new Set(prev);
            if (next.has(id)) {
                next.delete(id);
            } else {
                next.add(id);
            }
            return next;
        });
    }, []);

    const expandAll = useCallback((ids: number[]) => {
        setExpandedIds(new Set(ids));
    }, []);

    const collapseAll = useCallback(() => {
        setExpandedIds(new Set());
    }, []);

    return {
        expandedIds,
        expand,
        collapse,
        toggle,
        expandAll,
        collapseAll,
        isExpanded: (id: number) => expandedIds.has(id),
    };
}
